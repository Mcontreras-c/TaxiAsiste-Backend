from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import FilaBase, Movil
from .serializers import FilaBaseSerializer, MovilSerializer


class MovilViewSet(ModelViewSet):
    queryset = Movil.objects.select_related('socio').order_by('patente')
    serializer_class = MovilSerializer

    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        """Lista móviles con estado DISPONIBLE."""
        qs = self.queryset.filter(estado_operativo='DISPONIBLE')
        return Response(MovilSerializer(qs, many=True).data)


class FilaBaseViewSet(ModelViewSet):
    serializer_class = FilaBaseSerializer

    def get_queryset(self):
        """Por defecto muestra solo los EN_ESPERA; con ?todos=1 muestra el historial completo."""
        qs = FilaBase.objects.select_related('movil__socio').order_by('posicion')
        if self.request.query_params.get('todos', '0') != '1':
            return qs.filter(estado='EN_ESPERA')
        return qs

    def perform_create(self, serializer):
        """Asigna la posición automáticamente al ingresar a la fila."""
        ultima = (
            FilaBase.objects.filter(estado='EN_ESPERA')
            .order_by('-posicion')
            .values_list('posicion', flat=True)
            .first()
        )
        serializer.save(posicion=(ultima or 0) + 1)

    @action(detail=True, methods=['post'])
    def llamar(self, request, pk=None):
        """Paletero llama al móvil → estado LLAMADO."""
        from django.utils import timezone
        entrada = self.get_object()
        if entrada.estado != 'EN_ESPERA':
            return Response(
                {'detail': f'No se puede llamar un móvil en estado {entrada.estado}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entrada.estado = 'LLAMADO'
        entrada.fecha_llamado = timezone.now()
        entrada.save(update_fields=['estado', 'fecha_llamado'])
        return Response(FilaBaseSerializer(entrada).data)

    @action(detail=True, methods=['post'])
    def retirar(self, request, pk=None):
        """Móvil sale de la base → estado RETIRADO."""
        from django.utils import timezone
        entrada = self.get_object()
        if entrada.estado not in ('EN_ESPERA', 'LLAMADO'):
            return Response(
                {'detail': f'No se puede retirar un móvil en estado {entrada.estado}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entrada.estado = 'RETIRADO'
        entrada.fecha_salida = timezone.now()
        entrada.save(update_fields=['estado', 'fecha_salida'])
        return Response(FilaBaseSerializer(entrada).data)
