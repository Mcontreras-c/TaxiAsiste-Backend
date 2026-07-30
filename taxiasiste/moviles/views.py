from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from .models import FilaBase, Movil, UbicacionActual
from .serializers import FilaBaseSerializer, MovilSerializer, UbicacionActualSerializer

SEGUNDOS_ONLINE = 45


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
        serializer.save(posicion=(ultima or 0) + 1, fecha_ingreso=timezone.now())

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


class UbicacionActualViewSet(ReadOnlyModelViewSet):
    """
    Ubicacion GPS en tiempo real de los moviles. Solo lectura via API estandar
    (Central/mapa); el conductor reporta/borra su propia posicion via /mia/.
    """
    serializer_class = UbicacionActualSerializer

    def get_queryset(self):
        """Solo moviles que reportaron posicion en los ultimos SEGUNDOS_ONLINE (online)."""
        limite = timezone.now() - timedelta(seconds=SEGUNDOS_ONLINE)
        return (
            UbicacionActual.objects
            .select_related('movil__socio')
            .filter(actualizado_en__gte=limite)
        )

    @action(detail=False, methods=['post', 'delete'], url_path='mia')
    def mia(self, request):
        """El conductor autenticado reporta (POST) o borra (DELETE) su propia ubicacion."""
        from taxiasiste.socios.models import Socio

        try:
            socio = Socio.objects.get(usuario=request.user)
            movil = Movil.objects.get(socio=socio)
        except (Socio.DoesNotExist, Movil.DoesNotExist):
            return Response({'detail': 'No tienes un movil vinculado a tu cuenta.'}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'DELETE':
            UbicacionActual.objects.filter(movil=movil).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        lat = request.data.get('lat')
        lng = request.data.get('lng')
        if lat is None or lng is None:
            return Response({'detail': 'lat y lng son requeridos.'}, status=status.HTTP_400_BAD_REQUEST)

        ubicacion, _creada = UbicacionActual.objects.update_or_create(
            movil=movil,
            defaults={
                'lat': lat,
                'lng': lng,
                'heading': request.data.get('heading'),
                'velocidad_kmh': request.data.get('velocidad_kmh'),
                'actualizado_en': timezone.now(),
            },
        )
        return Response(UbicacionActualSerializer(ubicacion).data)
