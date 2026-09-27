"""
Baja y reactivacion de cuentas y socios.

Nunca se borra: una cuenta o un socio queda INACTIVO para no perder el
historial de viajes, pagos y reportes. Todo corre en una sola transaccion.
"""
from django.db import transaction
from django.utils import timezone

from taxiasiste.moviles.models import FilaBase, Movil, UbicacionActual
from taxiasiste.socios.models import Bloqueo, Socio
from taxiasiste.solicitudes.models import Reserva, ReservaEvento, Solicitud

from .models import Usuario


class BajaError(Exception):
    """Regla de negocio que impide la operacion (la vista responde 409)."""

    def __init__(self, detail):
        super().__init__(detail)
        self.detail = detail


def _es_administrador(usuario):
    return usuario.rol.nombre_rol == 'Administrador'


def _socio_de(usuario):
    try:
        return usuario.socio
    except Socio.DoesNotExist:
        return None


def _validar_usuario(usuario, solicitante):
    if solicitante is not None and usuario.id_usuario == solicitante.id_usuario:
        raise BajaError('No puedes darte de baja a ti mismo.')
    if _es_administrador(usuario) and usuario.estado == 'ACTIVO':
        otros = Usuario.objects.filter(rol=usuario.rol, estado='ACTIVO').exclude(pk=usuario.pk)
        if not otros.exists():
            raise BajaError('No se puede dar de baja al último administrador activo.')


def _inactivar_cuenta(usuario):
    usuario.estado = 'INACTIVO'
    # Sin sesion vigente. Ojo: la autenticacion rechaza ademas cualquier token
    # de un usuario no ACTIVO (UsuarioJWTAuthentication), porque una
    # sesion_actual vacia por si sola no invalida los tokens ya emitidos.
    usuario.sesion_actual = None
    usuario.save(update_fields=['estado', 'sesion_actual'])


@transaction.atomic
def dar_de_baja_usuario(usuario, solicitante):
    """
    Cuenta INACTIVA. Si es la cuenta de un conductor (tiene socio vinculado) la
    baja es la del socio completo: una persona no puede quedar con la cuenta
    inactiva y su movil operando en la fila.
    """
    if usuario.estado == 'INACTIVO':
        raise BajaError('El usuario ya está inactivo.')
    _validar_usuario(usuario, solicitante)

    socio = _socio_de(usuario)
    if socio is not None:
        _dar_de_baja_socio(socio)
    else:
        _inactivar_cuenta(usuario)
    return usuario


@transaction.atomic
def reactivar_usuario(usuario):
    if usuario.estado != 'INACTIVO':
        raise BajaError('El usuario no está inactivo.')
    socio = _socio_de(usuario)
    if socio is not None:
        _reactivar_socio(socio)
    else:
        usuario.estado = 'ACTIVO'
        usuario.save(update_fields=['estado'])
    return usuario


@transaction.atomic
def dar_de_baja_socio(socio, solicitante):
    if socio.estado_socio == 'INACTIVO':
        raise BajaError('El socio ya está inactivo.')
    if solicitante is not None and socio.usuario_id == solicitante.id_usuario:
        raise BajaError('No puedes darte de baja a ti mismo.')
    if socio.usuario is not None:
        _validar_usuario(socio.usuario, solicitante)
    _dar_de_baja_socio(socio)
    return socio


def _liberar_reservas(moviles):
    """
    Las reservas ASIGNADAS a los moviles del socio vuelven a quedar disponibles
    para que otro conductor las tome (con su rastro en RESERVA_EVENTOS). Las ya
    terminadas no se tocan: son historial.
    """
    for reserva in Reserva.objects.select_for_update().filter(movil__in=moviles, estado='ASIGNADA'):
        movil = reserva.movil
        reserva.estado = 'PROGRAMADA'
        reserva.movil = None
        reserva.fecha_tomada = None
        reserva.save(update_fields=['estado', 'movil', 'fecha_tomada'])
        ReservaEvento.objects.create(reserva=reserva, movil=movil, tipo='LIBERADA_POR_BAJA')


def _dar_de_baja_socio(socio):
    moviles = Movil.objects.filter(socio=socio)

    # Un viaje en curso quedaria sin conductor y el pasajero botado.
    if Solicitud.objects.filter(movil__in=moviles, estado__in=['ASIGNADO', 'EN_CURSO']).exists():
        raise BajaError('El socio tiene un viaje en curso. Termínalo o cancélalo antes de dar de baja.')

    # Igual con una reserva EN_CAMINO: el pasajero esta esperando al conductor.
    if Reserva.objects.filter(movil__in=moviles, estado='EN_CAMINO').exists():
        raise BajaError('El socio tiene una reserva en camino. Termínala o quítale la reserva antes de dar de baja.')

    _liberar_reservas(moviles)

    if socio.usuario is not None:
        _inactivar_cuenta(socio.usuario)

    socio.estado_socio = 'INACTIVO'
    socio.fecha_egreso = timezone.localdate()
    socio.save(update_fields=['estado_socio', 'fecha_egreso'])

    moviles.update(estado_operativo='INACTIVO')
    FilaBase.objects.filter(movil__in=moviles, estado__in=['EN_ESPERA', 'LLAMADO']).update(
        estado='RETIRADO', fecha_salida=timezone.now(),
    )
    UbicacionActual.objects.filter(movil__in=moviles).delete()


@transaction.atomic
def reactivar_socio(socio):
    if socio.estado_socio != 'INACTIVO':
        raise BajaError('El socio no está inactivo.')
    _reactivar_socio(socio)
    return socio


def _reactivar_socio(socio):
    # Si tenia un bloqueo vigente antes de la baja sigue bloqueado: reactivarlo
    # no debe levantar un bloqueo disciplinario o por cuotas.
    bloqueado = Bloqueo.objects.filter(socio=socio, activo=1).exists()

    if socio.usuario is not None:
        socio.usuario.estado = 'ACTIVO'
        socio.usuario.save(update_fields=['estado'])

    socio.estado_socio = 'BLOQUEADO' if bloqueado else 'ACTIVO'
    socio.fecha_egreso = None
    socio.save(update_fields=['estado_socio', 'fecha_egreso'])

    # No vuelve a la fila: entra el mismo cuando quiera.
    Movil.objects.filter(socio=socio, estado_operativo='INACTIVO').update(
        estado_operativo='BLOQUEADO' if bloqueado else 'DISPONIBLE',
    )
