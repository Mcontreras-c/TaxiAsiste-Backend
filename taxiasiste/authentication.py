from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class UsuarioJWTAuthentication(JWTAuthentication):
    """Resuelve el token JWT a un Usuario de Oracle en lugar de auth.User."""

    def get_user(self, validated_token):
        from taxiasiste.usuarios.models import Usuario
        try:
            user_id = validated_token['user_id']
            return Usuario.objects.select_related('rol').get(id_usuario=user_id)
        except Usuario.DoesNotExist:
            raise InvalidToken('Usuario no encontrado.')
