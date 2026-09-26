from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework import mixins

from taxiasiste.moviles.models import Movil
from taxiasiste.views import DIRECTIONS_URL, _resolver_punto, calcular_tarifa_estimada

from . import reservas_logic
from .models import DESTINO_UNICO, Pasajero, Reserva, ReservaEvento
from .serializers_reservas import ReservaCrearSerializer, ReservaSerializer

ROLES_CENTRAL = ('Administrador', 'Central')


def _rol(request):
    return getattr(getattr(request.user, 'rol', None), 'nombre_rol', None)


class EsCentral(BasePermission):
    """Administrador o Central: crean, cancelan y ven todas las reservas."""

    def has_permission(self, request, view):
        return _rol(request) in ROLES_CENTRAL


class EsConductor(BasePermission):
    """Conductor: ve las disponibles, toma y suelta las suyas."""

    def has_permission(self, request, view):
        return _rol(request) == 'Conductor'


def _movil_del_conductor(usuario):
    """
    Movil con el que el conductor toma reservas: el primero de su socio que no
    este BLOQUEADO. No se exige que este conectado ahora mismo (INACTIVO):
    reservar es comprometerse para mas tarde, no estar trabajando ya.
    """
    socio = getattr(usuario, 'socio', None)
    if socio is None or socio.estado_socio != 'ACTIVO':
        return None
    return socio.moviles.exclude(estado_operativo__in=['BLOQUEADO']).order_by('id_movil').first()


def _duracion_hacia_hospital(lat, lng, recogida):
    """
    Distancia y duracion origen -> hospital, con el trafico previsto para la
    hora de la reserva (departure_time futuro). Devuelve (distancia_m,
    duracion_s, error) con error None o 'red' / 'sin_ruta'.
    """
    try:
        resp = requests.get(
            DIRECTIONS_URL,
            params={
                'origin': f'{lat},{lng}',
                'destination': DESTINO_UNICO,
                'mode': 'driving',
                'departure_time': int(recogida.timestamp()),
                'region': 'cl',
                'key': settings.GOOGLE_MAPS_API_KEY,
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None, None, 'red'

    if data.get('status') != 'OK' or not data.get('routes'):
        return None, None, 'sin_ruta'
    leg = data['routes'][0]['legs'][0]
    duracion = (leg.get('duration_in_traffic') or leg['duration'])['value']
    return leg['distance']['value'], duracion, None


def _choque_con(reserva, activas):
    """Primera reserva de `activas` cuya franja se cruza con la de `reserva`, o None."""
    for otra in activas:
        if otra.pk == reserva.pk:
            continue
        if reservas_logic.se_cruzan(
            (reserva.fecha_hora_recogida, reserva.duracion_estimada_s),
            (otra.fecha_hora_recogida, otra.duracion_estimada_s),
        ):
            return otra
    return None


def _hora_local(dt):
    """HH:MM en 24 h para los mensajes de error (America/Santiago)."""
    from zoneinfo import ZoneInfo

    return reservas_logic.aware(dt).astimezone(ZoneInfo('America/Santiago')).strftime('%H:%M')


def _registrar(reserva, tipo, request, movil=None, detalle=None):
    ReservaEvento.objects.create(
        reserva=reserva, movil=movil, usuario=request.user, tipo=tipo, detalle=detalle,
    )


class ReservaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    queryset = Reserva.objects.select_related(
        'pasajero', 'movil__socio', 'usuario_central',
    ).order_by('fecha_hora_recogida')
    serializer_class = ReservaSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'create', 'cancelar'):
            return [IsAuthenticated(), EsCentral()]
        return [IsAuthenticated(), EsConductor()]

    # ---------------------------------------------------------------- Central

    def list(self, request):
        """
        Reservas para el panel de Central. Por defecto las vigentes
        (PROGRAMADA, ASIGNADA, EN_CAMINO); ?estado=X o ?estado=todas para otras.
        """
        estado = request.query_params.get('estado')
        qs = self.get_queryset()
        if estado == 'todas':
            pass
        elif estado:
            qs = qs.filter(estado=estado.upper())
        else:
            qs = qs.filter(estado__in=['PROGRAMADA', 'ASIGNADA', 'EN_CAMINO'])
        return Response(self.get_serializer(qs, many=True).data)

    def create(self, request):
        entrada = ReservaCrearSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        recogida = datos['fecha_hora_recogida']
        ahora = timezone.now()

        anticipacion = timedelta(minutes=settings.RESERVA_ANTICIPACION_MIN)
        horizonte = timedelta(hours=settings.RESERVA_HORIZONTE_HORAS)
        if recogida < ahora + anticipacion:
            return Response(
                {'detail': f'La reserva debe hacerse con al menos {settings.RESERVA_ANTICIPACION_MIN} minutos de anticipación.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if recogida > ahora + horizonte:
            return Response(
                {'detail': f'Solo se puede reservar hasta {settings.RESERVA_HORIZONTE_HORAS} horas hacia adelante.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pasajero = None
        if datos.get('pasajero') is not None:
            pasajero = Pasajero.objects.filter(pk=datos['pasajero']).first()
            if pasajero is None:
                return Response({'detail': 'El pasajero indicado no existe.'}, status=status.HTTP_400_BAD_REQUEST)

        punto, error = _resolver_punto(datos['origen'], None, None)
        if error == 'red':
            return Response({'detail': 'Servicio de ubicación no disponible. Intenta de nuevo.'},
                            status=status.HTTP_502_BAD_GATEWAY)
        if error:
            return Response({'detail': 'No se pudo ubicar la calle exacta del origen. Prueba con calle y número.'},
                            status=status.HTTP_404_NOT_FOUND)

        distancia_m, duracion_s, error = _duracion_hacia_hospital(punto['lat'], punto['lng'], recogida)
        if error == 'red':
            return Response({'detail': 'No se pudo calcular la duración del viaje. Intenta de nuevo.'},
                            status=status.HTTP_502_BAD_GATEWAY)
        if error:
            return Response({'detail': 'No se encontró una ruta desde ese origen al hospital.'},
                            status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            reserva = Reserva.objects.create(
                pasajero=pasajero,
                usuario_central=request.user,
                origen=datos['origen'],
                origen_lat=round(punto['lat'], 6),
                origen_lng=round(punto['lng'], 6),
                fecha_hora_recogida=recogida,
                duracion_estimada_s=duracion_s,
                distancia_estimada_m=distancia_m,
                tarifa_estimada=calcular_tarifa_estimada(distancia_m, duracion_s),
                observaciones=datos.get('observaciones') or None,
            )
            _registrar(reserva, 'CREADA', request)
        return Response(self.get_serializer(reserva).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        """La Central cancela una reserva que aun no se cumplio."""
        with transaction.atomic():
            reserva = Reserva.objects.select_for_update().get(pk=self.get_object().pk)
            if reserva.estado not in ('PROGRAMADA', 'ASIGNADA'):
                return Response(
                    {'detail': f'No se puede cancelar una reserva {reserva.estado.lower()}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            movil = reserva.movil
            reserva.estado = 'CANCELADA'
            reserva.fecha_termino = timezone.now()
            reserva.save(update_fields=['estado', 'fecha_termino'])
            _registrar(reserva, 'CANCELADA', request, movil=movil, detalle=request.data.get('motivo'))
        return Response(self.get_serializer(reserva).data)

    # -------------------------------------------------------------- Conductor

    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        """
        Reservas sin conductor que aun no pasaron su hora maxima de salida. Cada
        una trae `puede_tomar` y, si no puede, `motivo_bloqueo` (el margen con
        otra reserva suya, o el tope de reservas activas).
        """
        movil = _movil_del_conductor(request.user)
        ahora = timezone.now()
        candidatas = [
            r for r in self.get_queryset().filter(estado='PROGRAMADA', fecha_hora_recogida__gt=ahora)
            if reservas_logic.hora_maxima_salida(r.fecha_hora_recogida, r.duracion_estimada_s) > ahora
        ]
        activas = list(self._activas_de(movil)) if movil else []

        resultado = []
        for r in candidatas:
            item = ReservaSerializer(r, context={'ocultar_pasajero': True}).data
            motivo = None
            if movil is None:
                motivo = 'Tu cuenta no tiene un móvil disponible para tomar reservas.'
            elif len(activas) >= settings.RESERVA_MAX_ACTIVAS:
                motivo = f'Ya tienes {settings.RESERVA_MAX_ACTIVAS} reservas activas.'
            else:
                choque = _choque_con(r, activas)
                if choque:
                    motivo = (f'Se cruza con tu reserva de las {_hora_local(choque.fecha_hora_recogida)} '
                              f'({choque.folio}).')
            item['puede_tomar'] = motivo is None
            item['motivo_bloqueo'] = motivo
            resultado.append(item)
        return Response(resultado)

    @action(detail=False, methods=['get'])
    def mias(self, request):
        """Reservas activas del conductor (asignadas o en camino), con datos del pasajero."""
        movil = _movil_del_conductor(request.user)
        qs = self._activas_de(movil) if movil else []
        return Response(ReservaSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def tomar(self, request, pk=None):
        movil = _movil_del_conductor(request.user)
        if movil is None:
            return Response({'detail': 'Tu cuenta no tiene un móvil disponible para tomar reservas.'},
                            status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            # Se bloquea el movil (serializa las tomas de un mismo conductor:
            # dos toques seguidos no pueden superar el tope ni cruzar franjas)
            # y luego la reserva (dos conductores no pueden llevarse la misma).
            Movil.objects.select_for_update().get(pk=movil.pk)
            reserva = Reserva.objects.select_for_update().get(pk=self.get_object().pk)

            if reserva.estado != 'PROGRAMADA':
                return Response({'detail': 'Esta reserva ya no está disponible.'}, status=status.HTTP_409_CONFLICT)

            ahora = timezone.now()
            if reservas_logic.hora_maxima_salida(reserva.fecha_hora_recogida, reserva.duracion_estimada_s) <= ahora:
                return Response({'detail': 'Ya no alcanzas a llegar: pasó la hora máxima de salida para esta reserva.'},
                                status=status.HTTP_409_CONFLICT)

            activas = list(self._activas_de(movil))
            if len(activas) >= settings.RESERVA_MAX_ACTIVAS:
                return Response({'detail': f'Ya tienes {settings.RESERVA_MAX_ACTIVAS} reservas activas.'},
                                status=status.HTTP_409_CONFLICT)
            choque = _choque_con(reserva, activas)
            if choque:
                return Response(
                    {'detail': (f'Se cruza con tu reserva de las {_hora_local(choque.fecha_hora_recogida)} '
                                f'({choque.folio}). Deja {settings.RESERVA_MARGEN_MIN} minutos de margen entre viajes.')},
                    status=status.HTTP_409_CONFLICT,
                )

            reserva.estado = 'ASIGNADA'
            reserva.movil = movil
            reserva.fecha_tomada = ahora
            reserva.save(update_fields=['estado', 'movil', 'fecha_tomada'])
            _registrar(reserva, 'TOMADA', request, movil=movil)
        return Response(self.get_serializer(reserva).data)

    @action(detail=True, methods=['post'])
    def soltar(self, request, pk=None):
        """
        El conductor devuelve una reserva. Hasta RESERVA_SOLTAR_SIN_PENALIZACION_H
        horas antes de la recogida no hay consecuencia; despues se registra
        como SOLTADA_TARDE (base del registro de incumplimientos).
        """
        movil = _movil_del_conductor(request.user)
        with transaction.atomic():
            reserva = Reserva.objects.select_for_update().get(pk=self.get_object().pk)
            if movil is None or reserva.movil_id != movil.pk:
                return Response({'detail': 'Esta reserva no es tuya.'}, status=status.HTTP_403_FORBIDDEN)
            if reserva.estado != 'ASIGNADA':
                return Response({'detail': 'Solo se puede soltar una reserva que aún no está en camino.'},
                                status=status.HTTP_409_CONFLICT)

            limite = timedelta(hours=settings.RESERVA_SOLTAR_SIN_PENALIZACION_H)
            tarde = reservas_logic.aware(reserva.fecha_hora_recogida) - timezone.now() < limite

            reserva.estado = 'PROGRAMADA'
            reserva.movil = None
            reserva.fecha_tomada = None
            reserva.save(update_fields=['estado', 'movil', 'fecha_tomada'])
            _registrar(reserva, 'SOLTADA_TARDE' if tarde else 'SOLTADA', request, movil=movil)

        data = self.get_serializer(reserva).data
        data['soltada_tarde'] = tarde
        return Response(data)

    # ---------------------------------------------------------------- Interno

    def _activas_de(self, movil):
        return (
            self.get_queryset()
            .filter(movil=movil, estado__in=Reserva.ESTADOS_ACTIVOS)
            .order_by('fecha_hora_recogida')
        )
