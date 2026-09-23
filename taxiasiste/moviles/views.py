from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers, status
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
        """El conductor inicia sesion / vuelve a servicio → móvil pasa a
        DISPONIBLE, salvo que tenga un viaje ASIGNADO o EN_CURSO: la app llama
        a esto cada vez que arranca el ConductorProvider (login, o simplemente
        reabrir la app), y si el conductor lo hace en medio de un viaje esto
        no puede pisarle el EN_SERVICIO/EN_VIAJE que puso cambiar_estado — si
        no, el mapa de Central lo vuelve a mostrar verde ("libre") con un
        viaje activo."""
        movil = self.get_object()
        solicitud_activa = (
            movil.solicitudes.filter(estado__in=['ASIGNADO', 'EN_CURSO'])
            .order_by('-fecha_hora')
            .first()
        )
        if solicitud_activa is None:
            movil.estado_operativo = 'DISPONIBLE'
        elif solicitud_activa.estado == 'EN_CURSO':
            movil.estado_operativo = 'EN_VIAJE'
        else:
            movil.estado_operativo = 'EN_SERVICIO'
        movil.save(update_fields=['estado_operativo'])
        return Response(MovilSerializer(movil).data, status=status.HTTP_200_OK)


class FilaBaseViewSet(ModelViewSet):
    serializer_class = FilaBaseSerializer

    def get_queryset(self):
        """
        En el listado, por defecto muestra solo los EN_ESPERA (?todos=1 para el
        historial completo). Las acciones sobre un registro puntual (retrieve,
        llamar, retirar) buscan por id_fila en TODOS los estados — si no, un
        movil en LLAMADO nunca se podria retirar porque ya no matchea el
        filtro EN_ESPERA de la lista, y la accion nunca se aplica (queda
        pegado para siempre).
        """
        qs = FilaBase.objects.select_related('movil__socio').order_by('posicion')
        if self.action == 'list' and self.request.query_params.get('todos', '0') != '1':
            return qs.filter(estado='EN_ESPERA')
        return qs

    def perform_create(self, serializer):
        """Asigna la posición automáticamente al ingresar a la fila.

        Un móvil no puede tener dos entradas activas a la vez (evita duplicados
        por doble-tap o reintentos de red en 'Entrar a la fila').
        """
        movil = serializer.validated_data['movil']
        ya_activo = FilaBase.objects.filter(movil=movil, estado__in=['EN_ESPERA', 'LLAMADO']).exists()
        if ya_activo:
            raise serializers.ValidationError({'detail': 'Este móvil ya está en la fila.'})

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
        """Móvil sale de la base → estado RETIRADO."""
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
    Ubicacion GPS en tiempo real de los moviles, consumida por polling desde
    el frontend web (sin WebSockets). Solo lectura via API estandar (Central/
    mapa); el conductor reporta/borra su propia posicion via /mia/.
    """
    serializer_class = UbicacionActualSerializer

    def get_queryset(self):
        """Solo moviles que reportaron posicion en los ultimos SEGUNDOS_ONLINE (online)."""
        limite = timezone.now() - timedelta(seconds=SEGUNDOS_ONLINE)
        queryset = (
            UbicacionActual.objects
            .select_related('movil__socio')
            .filter(actualizado_en__gte=limite)
        )

        # Un conductor con un viaje activo solo ve su propio movil: no debe
        # conocer la posicion del resto de la flota mientras trabaja. No basta
        # con ocultarlos en la app, porque este endpoint los entregaria igual.
        usuario = self.request.user
        if usuario.rol.nombre_rol == 'Conductor':
            from taxiasiste.solicitudes.models import Solicitud

            if Solicitud.objects.filter(
                movil__socio__usuario=usuario, estado__in=['ASIGNADO', 'EN_CURSO'],
            ).exists():
                queryset = queryset.filter(movil__socio__usuario=usuario)
        return queryset

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
