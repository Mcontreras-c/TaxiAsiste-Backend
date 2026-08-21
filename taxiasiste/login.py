import uuid

from django.contrib.auth.hashers import check_password
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from taxiasiste.usuarios.models import Usuario


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class LoginView(APIView):
    """Login contra la tabla USUARIOS de Oracle. Devuelve access + refresh JWT."""
    permission_classes = [AllowAny]

    @extend_schema(
        request=LoginSerializer,
        examples=[
            OpenApiExample(
                'Ejemplo',
                value={'username': 'admin', 'password': 'Admin2026!'},
                request_only=True,
            )
        ],
    )
    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')

        if not username or not password:
            return Response(
                {'detail': 'username y password son requeridos.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            usuario = Usuario.objects.select_related('rol').get(username=username)
        except Usuario.DoesNotExist:
            return Response(
                {'detail': 'Credenciales incorrectas.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not check_password(password, usuario.password_hash):
            return Response(
                {'detail': 'Credenciales incorrectas.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if usuario.estado != 'ACTIVO':
            return Response(
                {'detail': f'Usuario {usuario.estado.lower()}. Contacte al administrador.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Sesion unica: este login invalida cualquier token emitido antes para
        # esta cuenta (otro dispositivo/pestaña con la sesion vieja quedara
        # con un 'sid' que ya no coincide y su token sera rechazado).
        sesion_id = uuid.uuid4().hex
        usuario.ultimo_acceso = timezone.now()
        usuario.sesion_actual = sesion_id
        usuario.save(update_fields=['ultimo_acceso', 'sesion_actual'])

        refresh = RefreshToken()
        refresh['user_id'] = usuario.id_usuario
        refresh['username'] = usuario.username
        refresh['rol'] = usuario.rol.nombre_rol
        refresh['sid'] = sesion_id

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'usuario': {
                'id_usuario': usuario.id_usuario,
                'username': usuario.username,
                'email': usuario.email,
                'rol': usuario.rol.nombre_rol,
                'estado': usuario.estado,
            },
        })
