from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

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

    @action(detail=False, methods=['get'])
    def pendientes(self, request):
        """Lista solicitudes en estado PENDIENTE."""
        qs = self.queryset.filter(estado='PENDIENTE')
        return Response(SolicitudListSerializer(qs, many=True).data)

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

        if nuevo_estado == 'EN_CURSO':
            solicitud.fecha_inicio = ahora
            update_fields.append('fecha_inicio')

        if nuevo_estado in ('COMPLETADO', 'CANCELADO'):
            solicitud.fecha_termino = ahora
            update_fields.append('fecha_termino')

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
