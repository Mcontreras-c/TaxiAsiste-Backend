from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class UsuarioJWTAuthentication(JWTAuthentication):
    """Resuelve el token JWT a un Usuario de Oracle en lugar de auth.User."""

    def get_user(self, validated_token):
        from taxiasiste.usuarios.models import Usuario
        try:
            user_id = validated_token['user_id']
            usuario = Usuario.objects.select_related('rol').get(id_usuario=user_id)
        except Usuario.DoesNotExist:
            raise InvalidToken('Usuario no encontrado.')

        # Sesion unica: si el 'sid' del token no coincide con la sesion activa
        # guardada en el usuario, es un token de una sesion vieja (se inicio
        # sesion despues en otro dispositivo) -> se rechaza.
        token_sid = validated_token.get('sid')
        if usuario.sesion_actual and token_sid != usuario.sesion_actual:
            raise InvalidToken('Sesión cerrada: se inició sesión en otro dispositivo.')

        return usuario
