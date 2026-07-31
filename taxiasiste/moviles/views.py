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
    queryset = Movil.objects.select_related('socio', 'ubicacion_actual').order_by('patente')

    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        """Lista móviles con estado DISPONIBLE."""
        qs = self.queryset.filter(estado_operativo='DISPONIBLE')
        return Response(MovilSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def ubicacion(self, request, pk=None):
        """Recibe la posición GPS del conductor y la retransmite por WebSocket a Central."""
        movil = self.get_object()
        serializer = UbicacionActualSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        UbicacionActual.objects.update_or_create(
            movil=movil,
            defaults={**serializer.validated_data, 'actualizado_en': timezone.now()},
        )

        payload = {
            'id_movil': movil.id_movil,
            'patente': movil.patente,
            'estado_operativo': movil.estado_operativo,
            **{k: (float(v) if v is not None else None) for k, v in serializer.validated_data.items()},
        }
        self._broadcast(payload)
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def desconectar(self, request, pk=None):
        """El conductor cierra sesion / sale de servicio → móvil pasa a INACTIVO."""
        movil = self.get_object()
        movil.estado_operativo = 'INACTIVO'
        movil.save(update_fields=['estado_operativo'])
        payload = self._payload_estado(movil)
        self._broadcast(payload)
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def conectar(self, request, pk=None):
        """El conductor inicia sesion / vuelve a servicio → móvil pasa a DISPONIBLE."""
        movil = self.get_object()
        movil.estado_operativo = 'DISPONIBLE'
        movil.save(update_fields=['estado_operativo'])
        payload = self._payload_estado(movil)
        self._broadcast(payload)
        return Response(payload, status=status.HTTP_200_OK)

    def perform_update(self, serializer):
        """
        Cubre cualquier otro camino de edicion (PATCH/PUT genericos desde el
        panel web, admin, etc.): si estado_operativo cambia, se retransmite
        por WebSocket igual que en las acciones dedicadas de arriba. Sin esto,
        Central solo se enteraba de cambios de estado que pasaran por
        /ubicacion/ o /desconectar/, y el mapa quedaba desactualizado ante
        cualquier otra forma de editar el movil.
        """
        estado_anterior = serializer.instance.estado_operativo
        movil = serializer.save()
        if movil.estado_operativo != estado_anterior:
            self._broadcast(self._payload_estado(movil))

    def _payload_estado(self, movil):
        """Arma el payload de broadcast, manteniendo la ultima posicion GPS conocida
        (si existe) para que el marcador no desaparezca del mapa, solo cambie de color."""
        try:
            ubicacion = movil.ubicacion_actual
            coords = {
                'lat': float(ubicacion.lat),
                'lng': float(ubicacion.lng),
                'heading': float(ubicacion.heading) if ubicacion.heading is not None else None,
                'velocidad_kmh': float(ubicacion.velocidad_kmh) if ubicacion.velocidad_kmh is not None else None,
            }
        except UbicacionActual.DoesNotExist:
            coords = {'lat': None, 'lng': None, 'heading': None, 'velocidad_kmh': None}

        return {
            'id_movil': movil.id_movil,
            'patente': movil.patente,
            'estado_operativo': movil.estado_operativo,
            **coords,
        }

    def _broadcast(self, payload):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'despacho',
            {'type': 'ubicacion.actualizada', 'data': payload},
        )


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
