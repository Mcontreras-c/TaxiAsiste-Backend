from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from taxiasiste.moviles import fila_logic
from taxiasiste.moviles.models import FilaBase, UbicacionActual


@pytest.fixture
def nuevo_movil(crear_usuario, crear_socio, crear_movil):
    """Crea un conductor con su socio y movil. Devuelve (usuario, movil)."""
    contador = {'n': 0}

    def _crear():
        contador['n'] += 1
        n = contador['n']
        usuario = crear_usuario(f'cond_fila{n}', rol_nombre='Conductor')
        socio = crear_socio(f'1{n:07d}-{n % 10}', usuario=usuario)
        movil = crear_movil(socio, f'FILA{n:02d}')
        return usuario, movil

    return _crear


@pytest.fixture
def entrar(nuevo_movil):
    """Pone un movil nuevo en la fila. Devuelve (usuario, movil, entrada)."""

    def _entrar(posicion, ingreso_hace_min=0, estado='EN_ESPERA', **extra):
        usuario, movil = nuevo_movil()
        entrada = FilaBase.objects.create(
            movil=movil, posicion=posicion, estado=estado,
            fecha_ingreso=timezone.now() - timedelta(minutes=ingreso_hace_min), **extra,
        )
        return usuario, movil, entrada

    return _entrar


def reportar_ubicacion(movil, hace_min):
    UbicacionActual.objects.create(
        movil=movil, lat=-33.45, lng=-70.66, actualizado_en=timezone.now() - timedelta(minutes=hace_min),
    )


def llamar_hace(entrada, segundos, **extra):
    FilaBase.objects.filter(pk=entrada.pk).update(
        estado='LLAMADO', fecha_llamado=timezone.now() - timedelta(seconds=segundos), **extra,
    )


# ============ Tarea 2: salida por inactividad ============

@pytest.mark.django_db
def test_sin_ubicacion_y_mas_de_5_min_en_la_fila_se_retira_por_inactividad(entrar):
    _, _, entrada = entrar(1, ingreso_hace_min=6)

    retirados = fila_logic.retirar_inactivos()

    entrada.refresh_from_db()
    assert retirados == 1
    assert entrada.estado == 'RETIRADO'
    assert entrada.motivo_salida == 'inactividad'
    assert entrada.fecha_salida is not None


@pytest.mark.django_db
def test_si_sigue_reportando_ubicacion_no_se_toca(entrar):
    _, movil, entrada = entrar(1, ingreso_hace_min=60)
    reportar_ubicacion(movil, hace_min=1)

    assert fila_logic.retirar_inactivos() == 0

    entrada.refresh_from_db()
    assert entrada.estado == 'EN_ESPERA' and entrada.motivo_salida is None


@pytest.mark.django_db
def test_ubicacion_vieja_de_una_sesion_anterior_no_saca_a_quien_recien_entro(entrar):
    """Referencia = la mas reciente entre el ultimo reporte y la entrada a la fila."""
    _, movil, entrada = entrar(1, ingreso_hace_min=1)
    reportar_ubicacion(movil, hace_min=120)

    assert fila_logic.retirar_inactivos() == 0

    entrada.refresh_from_db()
    assert entrada.estado == 'EN_ESPERA'


@pytest.mark.django_db
def test_ubicacion_vieja_y_entrada_vieja_se_retira(entrar):
    _, movil, entrada = entrar(1, ingreso_hace_min=30)
    reportar_ubicacion(movil, hace_min=10)

    assert fila_logic.retirar_inactivos() == 1

    entrada.refresh_from_db()
    assert entrada.estado == 'RETIRADO' and entrada.motivo_salida == 'inactividad'


@pytest.mark.django_db
def test_el_limite_es_estrictamente_mayor_a_5_minutos(entrar):
    _, _, entrada = entrar(1, ingreso_hace_min=5)
    ahora = entrada.fecha_ingreso + timedelta(minutes=5)

    assert fila_logic.retirar_inactivos(ahora) == 0
    assert fila_logic.retirar_inactivos(ahora + timedelta(seconds=1)) == 1


@pytest.mark.django_db
def test_no_toca_a_los_llamados_por_inactividad(entrar):
    _, _, entrada = entrar(1, ingreso_hace_min=60)
    llamar_hace(entrada, segundos=10)

    assert fila_logic.retirar_inactivos() == 0

    entrada.refresh_from_db()
    assert entrada.estado == 'LLAMADO'


@pytest.mark.django_db
def test_el_limite_de_inactividad_sale_de_settings(entrar, settings):
    settings.FILA_INACTIVIDAD_MIN = 20
    _, _, entrada = entrar(1, ingreso_hace_min=10)

    assert fila_logic.retirar_inactivos() == 0

    settings.FILA_INACTIVIDAD_MIN = 2
    assert fila_logic.retirar_inactivos() == 1


@pytest.mark.django_db
def test_el_comando_retira_a_los_inactivos_y_deja_a_los_activos(entrar):
    _, _, inactivo = entrar(1, ingreso_hace_min=20)
    _, movil, activo = entrar(2, ingreso_hace_min=20)
    reportar_ubicacion(movil, hace_min=0)
    salida = StringIO()

    call_command('retirar_inactivos_fila', stdout=salida)

    inactivo.refresh_from_db()
    activo.refresh_from_db()
    assert inactivo.estado == 'RETIRADO' and inactivo.motivo_salida == 'inactividad'
    assert activo.estado == 'EN_ESPERA'
    assert '1 retirado(s)' in salida.getvalue()


# ============ Tarea 3: llamado con "Voy" ============

@pytest.mark.django_db
def test_confirmar_a_tiempo_deja_al_movil_confirmado_y_sin_vencer(autenticar, entrar):
    usuario, _, entrada = entrar(1)
    llamar_hace(entrada, segundos=100, no_respuestas=1)

    resp = autenticar(usuario).post(f'/api/fila-base/{int(entrada.id_fila)}/confirmar/')

    assert resp.status_code == 200
    assert resp.data['confirmado'] is True
    assert resp.data['no_respuestas'] == 0  # confirmar una vez lo vuelve a 0
    assert resp.data['segundos_restantes'] is None

    # Aunque pase el plazo, un llamado confirmado no vence.
    assert fila_logic.procesar_llamados_vencidos(timezone.now() + timedelta(minutes=10)) == {'al_final': 0, 'retirados': 0}
    entrada.refresh_from_db()
    assert entrada.estado == 'LLAMADO'


@pytest.mark.django_db
def test_solo_el_dueno_del_movil_puede_confirmar(autenticar, entrar, nuevo_movil, crear_usuario):
    _, _, entrada = entrar(1)
    llamar_hace(entrada, segundos=10)
    otro_conductor, _ = nuevo_movil()
    paletero = crear_usuario('paletero_conf', rol_nombre='Paletero')

    for intruso in (otro_conductor, paletero):
        assert autenticar(intruso).post(f'/api/fila-base/{int(entrada.id_fila)}/confirmar/').status_code == 403

    entrada.refresh_from_db()
    assert entrada.confirmado_en is None


@pytest.mark.django_db
def test_confirmar_sin_haber_sido_llamado_es_400(autenticar, entrar):
    usuario, _, entrada = entrar(1)

    resp = autenticar(usuario).post(f'/api/fila-base/{int(entrada.id_fila)}/confirmar/')

    assert resp.status_code == 400


@pytest.mark.django_db
def test_confirmar_dos_veces_es_idempotente(autenticar, entrar):
    usuario, _, entrada = entrar(1)
    llamar_hace(entrada, segundos=10)
    cliente = autenticar(usuario)

    assert cliente.post(f'/api/fila-base/{int(entrada.id_fila)}/confirmar/').status_code == 200
    assert cliente.post(f'/api/fila-base/{int(entrada.id_fila)}/confirmar/').status_code == 200


@pytest.mark.django_db
def test_sin_confirmar_en_3_minutos_pasa_al_final_de_la_fila(entrar):
    _, _, primero = entrar(1)
    entrar(2)
    entrar(3)
    llamar_hace(primero, segundos=181)

    resultado = fila_logic.procesar_llamados_vencidos()

    primero.refresh_from_db()
    assert resultado == {'al_final': 1, 'retirados': 0}
    assert primero.estado == 'EN_ESPERA'
    assert primero.posicion == 4  # detras de los que estaban en 2 y 3
    assert primero.no_respuestas == 1
    assert primero.fecha_llamado is None
    assert primero.motivo_salida is None


@pytest.mark.django_db
def test_antes_de_los_3_minutos_no_pasa_nada(entrar):
    _, _, entrada = entrar(1)
    llamar_hace(entrada, segundos=170)

    assert fila_logic.procesar_llamados_vencidos() == {'al_final': 0, 'retirados': 0}

    entrada.refresh_from_db()
    assert entrada.estado == 'LLAMADO' and entrada.no_respuestas == 0


@pytest.mark.django_db
def test_dos_veces_seguidas_sin_confirmar_se_retira(entrar):
    _, _, entrada = entrar(1)
    llamar_hace(entrada, segundos=200)
    fila_logic.procesar_llamados_vencidos()  # 1a vez: al final
    entrada.refresh_from_db()
    assert entrada.estado == 'EN_ESPERA' and entrada.no_respuestas == 1

    llamar_hace(entrada, segundos=200)  # lo vuelven a llamar y otra vez no responde
    resultado = fila_logic.procesar_llamados_vencidos()

    entrada.refresh_from_db()
    assert resultado == {'al_final': 0, 'retirados': 1}
    assert entrada.estado == 'RETIRADO'
    assert entrada.motivo_salida == 'no_respondio'
    assert entrada.fecha_salida is not None


@pytest.mark.django_db
def test_confirmar_entre_medio_reinicia_el_contador(autenticar, entrar):
    usuario, _, entrada = entrar(1)
    llamar_hace(entrada, segundos=200)
    fila_logic.procesar_llamados_vencidos()  # no respondio: contador en 1
    cliente = autenticar(usuario)

    llamar_hace(entrada, segundos=10)
    cliente.post(f'/api/fila-base/{int(entrada.id_fila)}/confirmar/')  # confirma: vuelve a 0
    entrada.refresh_from_db()
    assert entrada.no_respuestas == 0

    # Un llamado posterior sin confirmar cuenta como la primera vez, no como la segunda.
    FilaBase.objects.filter(pk=entrada.pk).update(estado='EN_ESPERA', confirmado_en=None)
    llamar_hace(entrada, segundos=200)
    fila_logic.procesar_llamados_vencidos()
    entrada.refresh_from_db()
    assert entrada.estado == 'EN_ESPERA' and entrada.no_respuestas == 1


@pytest.mark.django_db
def test_confirmar_fuera_de_plazo_aplica_la_consecuencia_y_responde_409(autenticar, entrar):
    usuario, _, entrada = entrar(1)
    entrar(2)
    llamar_hace(entrada, segundos=200)

    resp = autenticar(usuario).post(f'/api/fila-base/{int(entrada.id_fila)}/confirmar/')

    assert resp.status_code == 409
    assert 'final de la fila' in resp.data['detail']
    entrada.refresh_from_db()
    assert entrada.estado == 'EN_ESPERA' and entrada.confirmado_en is None and entrada.posicion == 3


@pytest.mark.django_db
def test_confirmar_fuera_de_plazo_por_segunda_vez_avisa_que_salio_de_la_fila(autenticar, entrar):
    usuario, _, entrada = entrar(1)
    llamar_hace(entrada, segundos=200, no_respuestas=1)

    resp = autenticar(usuario).post(f'/api/fila-base/{int(entrada.id_fila)}/confirmar/')

    assert resp.status_code == 409
    assert 'saliste de la fila' in resp.data['detail']


@pytest.mark.django_db
def test_llamar_de_nuevo_reinicia_el_plazo_de_confirmacion(autenticar, entrar, crear_usuario):
    _, _, entrada = entrar(1)
    paletero = crear_usuario('paletero_llamar', rol_nombre='Paletero')
    FilaBase.objects.filter(pk=entrada.pk).update(confirmado_en=timezone.now(), no_respuestas=1)

    resp = autenticar(paletero).post(f'/api/fila-base/{int(entrada.id_fila)}/llamar/')

    assert resp.status_code == 200
    assert resp.data['confirmado'] is False
    assert resp.data['segundos_restantes'] == 180 or resp.data['segundos_restantes'] == 179


@pytest.mark.django_db
def test_el_listado_informa_los_segundos_que_quedan(autenticar, entrar, crear_usuario):
    _, _, entrada = entrar(1)
    llamar_hace(entrada, segundos=60)
    paletero = crear_usuario('paletero_lista', rol_nombre='Paletero')

    datos = autenticar(paletero).get('/api/fila-base/?todos=1').data

    fila = next(e for e in datos if e['id_fila'] == entrada.id_fila)
    assert 118 <= fila['segundos_restantes'] <= 120
    assert fila['llamado_vence_en'] is not None and fila['confirmado'] is False


@pytest.mark.django_db
def test_leer_la_fila_aplica_los_llamados_vencidos_sin_esperar_al_comando(autenticar, entrar, crear_usuario):
    _, _, entrada = entrar(1)
    llamar_hace(entrada, segundos=250)
    paletero = crear_usuario('paletero_vence', rol_nombre='Paletero')

    datos = autenticar(paletero).get('/api/fila-base/?todos=1').data

    fila = next(e for e in datos if e['id_fila'] == entrada.id_fila)
    assert fila['estado'] == 'EN_ESPERA' and fila['no_respuestas'] == 1


@pytest.mark.django_db
def test_el_comando_tambien_procesa_los_llamados_vencidos(entrar):
    _, _, entrada = entrar(1)
    llamar_hace(entrada, segundos=200)
    salida = StringIO()

    call_command('retirar_inactivos_fila', stdout=salida)

    entrada.refresh_from_db()
    assert entrada.estado == 'EN_ESPERA' and entrada.no_respuestas == 1
    assert '1 al final de la fila' in salida.getvalue()


@pytest.mark.django_db
def test_el_plazo_de_llamado_sale_de_settings(entrar, settings):
    settings.FILA_LLAMADO_SEGUNDOS = 30
    _, _, entrada = entrar(1)
    llamar_hace(entrada, segundos=45)

    assert fila_logic.procesar_llamados_vencidos()['al_final'] == 1
