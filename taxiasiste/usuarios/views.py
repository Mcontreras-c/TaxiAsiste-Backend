from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from .emails import enviar_aviso_cambio_correo, enviar_clave_temporal, enviar_credenciales_reenviadas
from .models import Rol, Usuario
from .passwords import generar_clave
from .permissions import EsAdministrador
from .serializers import PerfilEditarSerializer, PerfilSerializer, RolSerializer, UsuarioSerializer

PASSWORD_MIN_LEN = 6


class RolViewSet(ReadOnlyModelViewSet):
    queryset = Rol.objects.filter(activo=1)
    serializer_class = RolSerializer


class UsuarioViewSet(ModelViewSet):
    # select_related('socio'): reverse OneToOne (Socio.usuario) -- evita una
    # query aparte por fila cuando UsuarioSerializer.get_nombre_completo
    # busca el socio vinculado de cada usuario en el listado.
    queryset = Usuario.objects.select_related('rol', 'socio').all()
    serializer_class = UsuarioSerializer

    def get_permissions(self):
        if self.action == 'olvide_password':
            return [AllowAny()]
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'resetear_password', 'reenviar_credenciales'):
            return [EsAdministrador()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Devuelve el perfil del usuario autenticado."""
        serializer = UsuarioSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['get', 'patch'], url_path='mi_perfil')
    def mi_perfil(self, request):
        """
        Perfil de la propia cuenta. GET lo muestra; PATCH deja cambiar SOLO el
        correo y el telefono (nombre, RUT, usuario, rol y estado los maneja un
        administrador). Cambiar el correo exige la clave actual y avisa al
        correo anterior. Un Conductor guarda su telefono en su ficha de socio.
        """
        usuario = request.user
        if request.method == 'GET':
            return Response(PerfilSerializer(usuario).data)

        entrada = PerfilEditarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data

        correo_anterior = usuario.email
        correo_nuevo = datos.get('email')
        cambia_correo = correo_nuevo is not None and correo_nuevo.lower() != (correo_anterior or '').lower()

        if cambia_correo:
            if not check_password(datos.get('password_actual', ''), usuario.password_hash):
                return Response({'detail': 'Para cambiar el correo debes ingresar tu contraseña actual.'}, status=400)
            if Usuario.objects.filter(email__iexact=correo_nuevo).exclude(pk=usuario.pk).exists():
                return Response({'detail': 'Ese correo ya está en uso por otra cuenta.'}, status=400)
            usuario.email = correo_nuevo
            usuario.save(update_fields=['email'])

        if 'telefono' in datos:
            socio = PerfilSerializer.socio_de(usuario)
            if socio:
                socio.telefono = datos['telefono']
                socio.save(update_fields=['telefono'])
            else:
                usuario.telefono = datos['telefono']
                usuario.save(update_fields=['telefono'])

        if cambia_correo and correo_anterior:
            enviar_aviso_cambio_correo(usuario, correo_anterior, correo_nuevo)

        return Response(PerfilSerializer(usuario).data)

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
        nueva = request.data.get('password_nueva', '')
        if len(nueva) < PASSWORD_MIN_LEN:
            return Response({'detail': f'La nueva contraseña debe tener al menos {PASSWORD_MIN_LEN} caracteres.'}, status=400)

        usuario = self.get_object()
        usuario.password_hash = make_password(nueva)
        usuario.save(update_fields=['password_hash'])
        return Response({'detail': f'Contraseña de {usuario.username} actualizada correctamente.'})

    @action(detail=True, methods=['post'])
    def reenviar_credenciales(self, request, pk=None):
        """
        Un Administrador genera una clave nueva para una cuenta existente y se
        la manda por correo (con el link de la app o del panel segun el rol).
        La clave nunca se devuelve ni se muestra: solo viaja por el correo.
        """
        usuario = self.get_object()
        if not usuario.email:
            return Response({'detail': 'Este usuario no tiene correo registrado.'}, status=400)

        clave = generar_clave()
        clave_anterior = usuario.password_hash
        usuario.password_hash = make_password(clave)
        usuario.save(update_fields=['password_hash'])

        if not enviar_credenciales_reenviadas(usuario, clave):
            # Si el correo no salio, se restaura la clave anterior: sino la
            # persona quedaria con una clave que nadie conoce.
            usuario.password_hash = clave_anterior
            usuario.save(update_fields=['password_hash'])
            return Response(
                {'detail': 'No se pudo enviar el correo. La clave no se modificó.'},
                status=502,
            )
        return Response({'detail': f'Credenciales enviadas a {usuario.email}.'})

    @action(detail=False, methods=['post'])
    def olvide_password(self, request):
        """
        Vista publica de "olvide mi contrasena". Siempre responde el mismo
        mensaje generico, exista o no el correo, para no filtrar que correos
        estan registrados.
        """
        email = (request.data.get('email') or '').strip()
        mensaje_generico = 'Si la casilla de correo existe, te llegará un correo con una clave temporal.'

        if email:
            usuario = Usuario.objects.filter(email__iexact=email).select_related('rol').first()
            if usuario:
                clave_temporal = generar_clave()
                usuario.password_hash = make_password(clave_temporal)
                usuario.save(update_fields=['password_hash'])
                enviar_clave_temporal(usuario, clave_temporal)

        return Response({'detail': mensaje_generico})

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
