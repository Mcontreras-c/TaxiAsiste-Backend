from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from taxiasiste.views import calcular_ruta, geocodificar_direccion

from .models import Pasajero, Solicitud
from .serializers import (
    PasajeroSerializer,
    SolicitudListSerializer,
    SolicitudSerializer,
)

TRANSICIONES_VALIDAS = {
    'PENDIENTE':  ['ASIGNADO', 'CANCELADO'],
    'ASIGNADO':   ['EN_CURSO', 'CANCELADO'],
    'EN_CURSO':   ['COMPLETADO', 'CANCELADO'],
    'COMPLETADO': [],
    'CANCELADO':  [],
}


class PasajeroViewSet(ModelViewSet):
    queryset = Pasajero.objects.filter(activo=1).order_by('apellido', 'nombre')
    serializer_class = PasajeroSerializer

    @action(detail=True, methods=['post'])
    def levantar_bloqueo(self, request, pk=None):
        """Un administrador levanta el bloqueo de un pasajero y reinicia su contador de incumplimientos."""
        rol = getattr(getattr(request.user, 'rol', None), 'nombre_rol', None)
        if rol != 'Administrador':
            return Response({'detail': 'Solo un administrador puede levantar el bloqueo.'},
                            status=status.HTTP_403_FORBIDDEN)
        pasajero = self.get_object()
        pasajero.incumplimientos = 0
        pasajero.bloqueado_domicilio = 0
        pasajero.save(update_fields=['incumplimientos', 'bloqueado_domicilio'])
        return Response(PasajeroSerializer(pasajero).data)

    @action(detail=False, methods=['get'])
    def buscar_rut(self, request):
        """Autocompletar por RUT en la central."""
        rut = request.query_params.get('rut', '').strip()
        if not rut:
            return Response(
                {'detail': 'Parámetro rut requerido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = self.queryset.filter(rut__icontains=rut)
        return Response(PasajeroSerializer(qs, many=True).data)


class SolicitudViewSet(ModelViewSet):
    queryset = Solicitud.objects.select_related(
        'pasajero', 'movil', 'usuario_central'
    ).order_by('-fecha_hora')
    serializer_class = SolicitudSerializer

    def get_serializer_class(self):
        if self.action == 'list':
            return SolicitudListSerializer
        return SolicitudSerializer

    def perform_create(self, serializer):
        """
        Un pasajero bloqueado por incumplimientos no puede pedir un movil a
        domicilio (telefono/app); en el hospital (PRESENCIAL) si.

        Geocodifica el origen al crear -- best-effort, nunca bloquea la
        creacion aunque Google falle o no encuentre la direccion (queda con
        origen_lat/lng null, y pendientes_con_distancia simplemente no puede
        calcularle distancia/ETA a esa solicitud puntual).
        """
        pasajero = serializer.validated_data.get('pasajero')
        if pasajero and pasajero.bloqueado_domicilio and serializer.validated_data.get('canal_entrada') != 'PRESENCIAL':
            from .views_reservas import MENSAJE_PASAJERO_BLOQUEADO
            raise ValidationError({'detail': MENSAJE_PASAJERO_BLOQUEADO})

        solicitud = serializer.save()
        lat, lng, _direccion_formateada, _error = geocodificar_direccion(solicitud.origen)
        if lat is not None:
            solicitud.origen_lat = lat
            solicitud.origen_lng = lng
            solicitud.save(update_fields=['origen_lat', 'origen_lng'])

    @action(detail=False, methods=['get'])
    def pendientes(self, request):
        """Lista solicitudes en estado PENDIENTE."""
        qs = self.queryset.filter(estado='PENDIENTE')
        return Response(SolicitudListSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def pendientes_con_distancia(self, request):
        """
        Lista solicitudes PENDIENTE ordenadas por mayor tiempo de espera
        primero (fecha_hora ascendente), con distancia_km/duracion_min desde
        la posicion actual del conductor (lat/lng) hasta el punto de recogida
        de cada una -- para la pantalla "Solicitudes pendientes" de Mobile
        (ver SolicitudesScreen.tsx).

        Se calcula una llamada a Directions API por cada solicitud pendiente
        con origen geocodificado, solo cuando el conductor abre/refresca esta
        pantalla (no hay polling automatico) -- a proposito, para no gastar
        cuota de Google en cada actualizacion silenciosa.
        """
        try:
            lat = float(request.query_params['lat'])
            lng = float(request.query_params['lng'])
        except (KeyError, ValueError):
            return Response(
                {'detail': 'Se requieren lat y lng (numericos) con la posicion actual del conductor.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = self.queryset.filter(estado='PENDIENTE').order_by('fecha_hora')
        resultado = []
        for solicitud in qs:
            item = SolicitudListSerializer(solicitud).data
            item['distancia_km'] = None
            item['duracion_min'] = None
            if solicitud.origen_lat is not None and solicitud.origen_lng is not None:
                data, error = calcular_ruta(lat, lng, float(solicitud.origen_lat), float(solicitud.origen_lng))
                if not error:
                    leg = data['routes'][0]['legs'][0]
                    item['distancia_km'] = round(leg['distance']['value'] / 1000, 1)
                    item['duracion_min'] = round(leg['duration']['value'] / 60)
            resultado.append(item)

        return Response(resultado)

    @action(detail=False, methods=['get'])
    def en_curso(self, request):
        """Lista solicitudes activas (ASIGNADO o EN_CURSO)."""
        qs = self.queryset.filter(estado__in=['ASIGNADO', 'EN_CURSO'])
        return Response(SolicitudListSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """Transición de estado validada según el flujo del negocio."""
        solicitud = self.get_object()
        nuevo_estado = request.data.get('estado', '').upper()
        movil_id = request.data.get('movil')

        estados_posibles = TRANSICIONES_VALIDAS.get(solicitud.estado, [])
        if nuevo_estado not in estados_posibles:
            return Response(
                {
                    'detail': (
                        f'Transición inválida: {solicitud.estado} → {nuevo_estado}. '
                        f'Estados posibles: {estados_posibles}'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ahora = timezone.now()
        update_fields = ['estado']
        solicitud.estado = nuevo_estado

        if nuevo_estado == 'ASIGNADO':
            if not movil_id:
                return Response(
                    {'detail': 'Se requiere movil para asignar.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            solicitud.movil_id = movil_id
            solicitud.fecha_asignacion = ahora
            update_fields += ['movil_id', 'fecha_asignacion']
            # El conductor tomo la solicitud y va en camino a buscar al
            # pasajero -> el mapa de Central ya debe dejar de mostrarlo
            # DISPONIBLE (verde) aunque el viaje todavia no arranco. Solo si
            # estaba DISPONIBLE: no pisa un BLOQUEADO/INACTIVO puesto a mano.
            if solicitud.movil and solicitud.movil.estado_operativo == 'DISPONIBLE':
                solicitud.movil.estado_operativo = 'EN_SERVICIO'
                solicitud.movil.save(update_fields=['estado_operativo'])

        if nuevo_estado == 'EN_CURSO':
            solicitud.fecha_inicio = ahora
            update_fields.append('fecha_inicio')
            # El pasajero ya esta a bordo -> el movil pasa a EN_VIAJE, un
            # estado/color distinto de EN_SERVICIO (que ahora significa "voy
            # en camino a buscarlo", puesto en el bloque ASIGNADO de arriba).
            # Acepta DISPONIBLE tambien por si esta transicion se dispara sin
            # haber pasado por el flujo normal de ASIGNADO (ver tests).
            if solicitud.movil and solicitud.movil.estado_operativo in ('DISPONIBLE', 'EN_SERVICIO'):
                solicitud.movil.estado_operativo = 'EN_VIAJE'
                solicitud.movil.save(update_fields=['estado_operativo'])

        if nuevo_estado in ('COMPLETADO', 'CANCELADO'):
            solicitud.fecha_termino = ahora
            update_fields.append('fecha_termino')
            # Simetrico a los bloques de arriba: el viaje termino (o se
            # cancelo estando ya ASIGNADO o EN_CURSO) -> vuelve a DISPONIBLE,
            # pero solo si el estado actual es justo uno de los que este
            # mismo flujo puso (EN_SERVICIO o EN_VIAJE) -- evita reactivar un
            # movil que Central desconecto/bloqueo mientras tanto.
            if solicitud.movil and solicitud.movil.estado_operativo in ('EN_SERVICIO', 'EN_VIAJE'):
                solicitud.movil.estado_operativo = 'DISPONIBLE'
                solicitud.movil.save(update_fields=['estado_operativo'])

        observacion = request.data.get('observacion')
        if observacion:
            solicitud.observaciones = observacion
            update_fields.append('observaciones')

        solicitud.save(update_fields=update_fields)
        return Response(SolicitudSerializer(solicitud).data)

    @action(detail=False, methods=['get'])
    def resumen_central(self, request):
        """Resumen para la Central: pendientes, en curso y últimas 4 finalizadas."""
        pendientes  = self.queryset.filter(estado='PENDIENTE')
        en_curso    = self.queryset.filter(estado__in=['ASIGNADO', 'EN_CURSO'])
        finalizadas = self.queryset.filter(estado__in=['COMPLETADO', 'CANCELADO'])[:4]
        return Response({
            'pendientes':  SolicitudListSerializer(pendientes, many=True).data,
            'en_curso':    SolicitudListSerializer(en_curso, many=True).data,
            'finalizadas': SolicitudListSerializer(finalizadas, many=True).data,
        })
