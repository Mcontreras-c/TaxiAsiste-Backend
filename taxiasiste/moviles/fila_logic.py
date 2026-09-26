"""
Reglas de la fila virtual que se aplican con el paso del tiempo:

* Salida por inactividad: un movil EN_ESPERA que lleva mas de FILA_INACTIVIDAD_MIN
  minutos sin reportar ubicacion se retira (motivo_salida='inactividad').
* Llamado con "Voy": el conductor llamado tiene FILA_LLAMADO_SEGUNDOS para confirmar.
  Si no lo hace pasa al final de la fila; si le ocurre dos veces seguidas se retira
  (motivo_salida='no_respondio'). Confirmar una vez vuelve el contador a 0.

Todas las funciones reciben `ahora` para poder probarlas sin esperar. Cada entrada se
procesa dentro de una transaccion con select_for_update, asi el comando programado y el
chequeo al leer la fila no se pisan.
"""
from datetime import timedelta, timezone as dt_timezone

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import FilaBase

MAX_NO_RESPUESTAS = 2


def _ahora(ahora):
    return ahora or timezone.now()


def _con_zona(fecha):
    """
    Las columnas de la fila son TIMESTAMP sin zona: Postgres las devuelve como datetime
    'naive' (siempre en UTC, ver TIME_ZONE en settings), y no se pueden comparar con
    timezone.now(). Se les pone UTC explicitamente.
    """
    if fecha is not None and timezone.is_naive(fecha):
        return timezone.make_aware(fecha, dt_timezone.utc)
    return fecha


def vence_llamado(entrada):
    """Momento limite para confirmar, o None si no aplica (no llamado o ya confirmado)."""
    if entrada.estado != 'LLAMADO' or entrada.confirmado_en or not entrada.fecha_llamado:
        return None
    return _con_zona(entrada.fecha_llamado) + timedelta(seconds=settings.FILA_LLAMADO_SEGUNDOS)


def segundos_restantes(entrada, ahora=None):
    vence = vence_llamado(entrada)
    if vence is None:
        return None
    return max(0, int((vence - _ahora(ahora)).total_seconds()))


# ---------- inactividad ----------

def _ultima_actividad(entrada):
    """
    Referencia de 'ultima actividad' de un movil en la fila: su ultimo reporte de
    ubicacion, pero nunca antes de que entrara a la fila (una ubicacion vieja de una
    sesion anterior no debe sacarlo apenas entra).
    """
    referencia = _con_zona(entrada.fecha_ingreso)
    try:
        ubicacion = entrada.movil.ubicacion_actual
    except ObjectDoesNotExist:
        return referencia
    reporte = _con_zona(ubicacion.actualizado_en)
    if reporte and reporte > referencia:
        return reporte
    return referencia


def retirar_inactivos(ahora=None):
    """Retira los EN_ESPERA sin actividad por mas del limite. Devuelve cuantos retiro."""
    ahora = _ahora(ahora)
    limite = timedelta(minutes=settings.FILA_INACTIVIDAD_MIN)
    candidatos = FilaBase.objects.filter(estado='EN_ESPERA').select_related('movil__ubicacion_actual')

    retirados = 0
    for entrada in candidatos:
        if ahora - _ultima_actividad(entrada) <= limite:
            continue
        with transaction.atomic():
            actual = FilaBase.objects.select_for_update().get(pk=entrada.pk)
            # Otro proceso pudo haberla llamado o retirado entre la lectura y el bloqueo.
            if actual.estado != 'EN_ESPERA':
                continue
            actual.estado = 'RETIRADO'
            actual.fecha_salida = ahora
            actual.motivo_salida = 'inactividad'
            actual.save(update_fields=['estado', 'fecha_salida', 'motivo_salida'])
            retirados += 1
    return retirados


# ---------- llamado con "Voy" ----------

def _vencer_si_corresponde(pk, ahora):
    """
    Si la entrada esta LLAMADA, sin confirmar y con el plazo agotado, la manda al final
    de la fila o la retira. Devuelve 'al_final', 'retirado' o None si no correspondia.
    """
    with transaction.atomic():
        entrada = FilaBase.objects.select_for_update().get(pk=pk)
        vence = vence_llamado(entrada)
        if vence is None or vence > ahora:
            return None

        entrada.no_respuestas += 1
        if entrada.no_respuestas >= MAX_NO_RESPUESTAS:
            entrada.estado = 'RETIRADO'
            entrada.fecha_salida = ahora
            entrada.motivo_salida = 'no_respondio'
            entrada.save(update_fields=['no_respuestas', 'estado', 'fecha_salida', 'motivo_salida'])
            return 'retirado'

        ultima = FilaBase.objects.filter(estado='EN_ESPERA').aggregate(m=Max('posicion'))['m']
        entrada.estado = 'EN_ESPERA'
        entrada.posicion = (ultima or 0) + 1
        entrada.fecha_llamado = None
        entrada.save(update_fields=['no_respuestas', 'estado', 'posicion', 'fecha_llamado'])
        return 'al_final'


def procesar_llamados_vencidos(ahora=None):
    """Aplica el plazo de 'Voy' a todos los llamados vencidos. Devuelve {'al_final': n, 'retirados': n}."""
    ahora = _ahora(ahora)
    limite = ahora - timedelta(seconds=settings.FILA_LLAMADO_SEGUNDOS)
    pks = list(
        FilaBase.objects.filter(estado='LLAMADO', confirmado_en__isnull=True, fecha_llamado__lte=limite)
        .order_by('fecha_llamado')
        .values_list('pk', flat=True)
    )
    resultado = {'al_final': 0, 'retirados': 0}
    for pk in pks:
        efecto = _vencer_si_corresponde(pk, ahora)
        if efecto == 'al_final':
            resultado['al_final'] += 1
        elif efecto == 'retirado':
            resultado['retirados'] += 1
    return resultado


def confirmar_llamado(pk, ahora=None):
    """
    El conductor pulsa "Voy". Devuelve (entrada, resultado) con resultado en:
    'confirmado', 'ya_confirmado', 'vencido' (se le acabo el tiempo: ya paso al final o se
    retiro) o 'no_llamado' (la entrada no esta en estado LLAMADO).
    """
    ahora = _ahora(ahora)
    with transaction.atomic():
        entrada = FilaBase.objects.select_for_update().get(pk=pk)
        if entrada.estado != 'LLAMADO':
            return entrada, 'no_llamado'
        if entrada.confirmado_en:
            return entrada, 'ya_confirmado'

        vence = vence_llamado(entrada)
        if vence is not None and vence <= ahora:
            # Plazo agotado: se aplica la consecuencia aunque el comando aun no haya corrido.
            _vencer_si_corresponde(pk, ahora)
            return FilaBase.objects.get(pk=pk), 'vencido'

        entrada.confirmado_en = ahora
        entrada.no_respuestas = 0
        entrada.save(update_fields=['confirmado_en', 'no_respuestas'])
        return entrada, 'confirmado'
