from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from .models import FilaBase, Movil, UbicacionActual
from .permissions import EsPropietarioDelMovilOStaff
from .serializers import FilaBaseSerializer, MovilSerializer, UbicacionActualSerializer

SEGUNDOS_ONLINE = 45


class MovilViewSet(ModelViewSet):
    queryset = Movil.objects.select_related('socio', 'ubicacion_actual').order_by('patente')
    serializer_class = MovilSerializer
    permission_classes = [IsAuthenticated, EsPropietarioDelMovilOStaff]

    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        """Lista móviles con estado DISPONIBLE."""
        qs = self.queryset.filter(estado_operativo='DISPONIBLE')
        return Response(MovilSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def ubicacion(self, request, pk=None):
        """Recibe la posición GPS del conductor (REST puro; Central la ve via polling a /api/ubicaciones/)."""
        movil = self.get_object()
        serializer = UbicacionActualSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        UbicacionActual.objects.update_or_create(
            movil=movil,
            defaults={**serializer.validated_data, 'actualizado_en': timezone.now()},
        )
        return Response(MovilSerializer(movil).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def desconectar(self, request, pk=None):
        """El conductor cierra sesion / sale de servicio → móvil pasa a INACTIVO."""
        movil = self.get_object()
        movil.estado_operativo = 'INACTIVO'
        movil.save(update_fields=['estado_operativo'])
        return Response(MovilSerializer(movil).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def conectar(self, request, pk=None):
        """El conductor inicia sesion / vuelve a servicio → móvil pasa a DISPONIBLE."""
        movil = self.get_object()
        movil.estado_operativo = 'DISPONIBLE'
        movil.save(update_fields=['estado_operativo'])
        return Response(MovilSerializer(movil).data, status=status.HTTP_200_OK)


class FilaBaseViewSet(ModelViewSet):
    serializer_class = FilaBaseSerializer

    def get_queryset(self):
        """Por defecto el LISTADO muestra solo los EN_ESPERA; con ?todos=1 muestra
        el historial completo. Las acciones sobre un registro puntual (llamar,
        retirar, retrieve) NO deben filtrarse por estado: si no, buscar una
        entrada LLAMADO (que el listado sin ?todos=1 excluye) da 404 y la
        accion nunca se aplica, dejando el registro pegado para siempre.
        """
        qs = FilaBase.objects.select_related('movil__socio').order_by('posicion')
        if self.action == 'list' and self.request.query_params.get('todos', '0') != '1':
            return qs.filter(estado='EN_ESPERA')
        return qs

    def create(self, request, *args, **kwargs):
        """Evita duplicados: un movil no puede tener dos entradas activas en la fila."""
        movil_id = request.data.get('movil')
        ya_en_fila = FilaBase.objects.filter(movil_id=movil_id, estado__in=['EN_ESPERA', 'LLAMADO']).first()
        if ya_en_fila:
            return Response(FilaBaseSerializer(ya_en_fila).data, status=status.HTTP_200_OK)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Asigna la posición automáticamente al ingresar a la fila.

        El chequeo de duplicados (móvil ya con entrada activa) vive en
        create(), que intercepta antes de llegar acá.
        """
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
        """Móvil sale de la base → estado RETIRADO, y se recorre la posición del resto."""
        entrada = self.get_object()
        if entrada.estado not in ('EN_ESPERA', 'LLAMADO'):
            return Response(
                {'detail': f'No se puede retirar un móvil en estado {entrada.estado}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entrada.estado = 'RETIRADO'
        entrada.fecha_salida = timezone.now()
        entrada.save(update_fields=['estado', 'fecha_salida'])

        # Re-numera al resto de la fila (EN_ESPERA) por orden de llegada, para
        # que no queden "huecos" en las posiciones (ej: 2, 3, 4 en vez de 1, 2, 3).
        restantes = FilaBase.objects.filter(estado='EN_ESPERA').order_by('fecha_ingreso')
        for nueva_posicion, fila in enumerate(restantes, start=1):
            if fila.posicion != nueva_posicion:
                fila.posicion = nueva_posicion
                fila.save(update_fields=['posicion'])

        return Response(FilaBaseSerializer(entrada).data)


class UbicacionActualViewSet(ReadOnlyModelViewSet):
    """
    Ubicacion GPS en tiempo real de los moviles, consumida por polling desde
    el frontend web (sin WebSockets). Solo lectura via API estandar (Central/
    mapa); el conductor reporta/borra su propia posicion via /mia/.
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

        serializer = UbicacionActualSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ubicacion, _creada = UbicacionActual.objects.update_or_create(
            movil=movil,
            defaults={**serializer.validated_data, 'actualizado_en': timezone.now()},
        )
        return Response(UbicacionActualSerializer(ubicacion).data)
