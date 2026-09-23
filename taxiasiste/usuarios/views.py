from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from .models import Rol, Usuario
from .serializers import PASSWORD_MIN_LEN, RolSerializer, UsuarioSerializer


class RolViewSet(ReadOnlyModelViewSet):
    queryset = Rol.objects.filter(activo=1)
    serializer_class = RolSerializer


class UsuarioViewSet(ModelViewSet):
    # select_related('socio'): reverse OneToOne (Socio.usuario) -- evita una
    # query aparte por fila cuando UsuarioSerializer.get_nombre_completo
    # busca el socio vinculado de cada usuario en el listado.
    queryset = Usuario.objects.select_related('rol', 'socio').all()
    serializer_class = UsuarioSerializer

    def create(self, request, *args, **kwargs):
        """Alta de usuario -- solo un Administrador puede crear cuentas
        nuevas (mismo criterio de sensibilidad que resetear_password)."""
        if request.user.rol.nombre_rol != 'Administrador':
            return Response({'detail': 'Solo un administrador puede crear usuarios.'}, status=403)
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Devuelve el perfil del usuario autenticado."""
        serializer = UsuarioSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def cambiar_password(self, request):
        """El usuario autenticado cambia su propia contraseña (pide la actual)."""
        actual = request.data.get('password_actual', '')
        nueva = request.data.get('password_nueva', '')

        if not actual or not nueva:
            return Response({'detail': 'password_actual y password_nueva son requeridos.'}, status=400)
        if len(nueva) < PASSWORD_MIN_LEN:
            return Response({'detail': f'La nueva contraseña debe tener al menos {PASSWORD_MIN_LEN} caracteres.'}, status=400)

        usuario = request.user
        if not check_password(actual, usuario.password_hash):
            return Response({'detail': 'La contraseña actual no es correcta.'}, status=400)

        usuario.password_hash = make_password(nueva)
        usuario.save(update_fields=['password_hash'])
        return Response({'detail': 'Contraseña actualizada correctamente.'})

    @action(detail=True, methods=['post'])
    def resetear_password(self, request, pk=None):
        """Un Administrador resetea la contraseña de cualquier usuario, sin pedir la actual."""
        if request.user.rol.nombre_rol != 'Administrador':
            return Response({'detail': 'Solo un administrador puede resetear contraseñas.'}, status=403)

        nueva = request.data.get('password_nueva', '')
        if len(nueva) < PASSWORD_MIN_LEN:
            return Response({'detail': f'La nueva contraseña debe tener al menos {PASSWORD_MIN_LEN} caracteres.'}, status=400)

        usuario = self.get_object()
        usuario.password_hash = make_password(nueva)
        usuario.save(update_fields=['password_hash'])
        return Response({'detail': f'Contraseña de {usuario.username} actualizada correctamente.'})

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
