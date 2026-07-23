from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from .models import Rol, Usuario
from .serializers import RolSerializer, UsuarioSerializer


class RolViewSet(ReadOnlyModelViewSet):
    queryset = Rol.objects.filter(activo=1)
    serializer_class = RolSerializer


class UsuarioViewSet(ModelViewSet):
    queryset = Usuario.objects.select_related('rol').all()
    serializer_class = UsuarioSerializer

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Devuelve el perfil del usuario autenticado."""
        serializer = UsuarioSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def perfil_conductor(self, request):
        """Datos del conductor: socio, móvil, solicitudes del día y cuotas."""
        from taxiasiste.socios.models import Socio, Cuota
        from taxiasiste.socios.serializers import SocioSerializer, CuotaSerializer
        from taxiasiste.moviles.models import Movil
        from taxiasiste.moviles.serializers import MovilSerializer
        from taxiasiste.solicitudes.models import Solicitud
        from taxiasiste.solicitudes.serializers import SolicitudListSerializer

        try:
            socio = Socio.objects.get(usuario=request.user)
        except Socio.DoesNotExist:
            return Response({'error': 'No tienes un socio vinculado a tu usuario.'}, status=404)

        movil = Movil.objects.filter(socio=socio).first()

        from django.db.models import Q

        hoy = timezone.now().date()
        solicitudes_hoy = []
        if movil:
            # Incluye lo del dia (por fecha del pedido) y ademas cualquier viaje
            # activo del movil sin importar cuando se creo la solicitud original.
            solicitudes_hoy = Solicitud.objects.filter(
                Q(fecha_hora__date=hoy) | Q(estado__in=['ASIGNADO', 'EN_CURSO']),
                movil=movil,
            ).order_by('-fecha_hora')

        cuotas = Cuota.objects.filter(socio=socio).order_by('-periodo')

        return Response({
            'socio':          SocioSerializer(socio).data,
            'movil':          MovilSerializer(movil).data if movil else None,
            'solicitudes_hoy': SolicitudListSerializer(solicitudes_hoy, many=True).data,
            'cuotas':         CuotaSerializer(cuotas, many=True).data,
            'fecha':          hoy.isoformat(),
        })
