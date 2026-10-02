"""
Confirmacion con contrasena ("step-up") para acciones sensibles.

Una sesion abierta y sin vigilar no alcanza para editar, dar de baja o bloquear:
el administrador vuelve a escribir su clave (POST /usuarios/confirmar_identidad/)
y recibe un permiso firmado de vida corta que el servidor exige, en el header
X-Confirmacion, en cada accion sensible. Va atado al usuario y a su sesion
(sid), asi que no sirve para otra persona ni sobrevive a un cierre de sesion.
"""
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core import signing
from django.core.cache import cache
from rest_framework.permissions import BasePermission

SAL = 'taxiasiste.confirmacion'
HEADER = 'HTTP_X_CONFIRMACION'


def _duracion():
    return getattr(settings, 'CONFIRMACION_SEGUNDOS', 120)


def _huella(usuario):
    return f'{usuario.pk}:{usuario.sesion_actual or ""}'


def emitir_token(usuario):
    return signing.TimestampSigner(salt=SAL).sign(_huella(usuario))


def token_valido(usuario, token):
    if not token:
        return False
    try:
        valor = signing.TimestampSigner(salt=SAL).unsign(token, max_age=_duracion())
    except signing.BadSignature:
        return False
    return valor == _huella(usuario)


class RequiereConfirmacion(BasePermission):
    message = 'Confirma tu contraseña para realizar esta acción.'

    def has_permission(self, request, view):
        return token_valido(request.user, request.META.get(HEADER))


# ── Intentos: 5 claves incorrectas seguidas bloquean unos minutos ────────────
def _clave_fallos(usuario):
    return f'confirmacion-fallos:{usuario.pk}'


def bloqueado(usuario):
    return cache.get(_clave_fallos(usuario), 0) >= settings.CONFIRMACION_MAX_INTENTOS


def verificar_password(usuario, password):
    """True si la clave es correcta (y reinicia el contador); False y suma un fallo si no."""
    if bloqueado(usuario):
        return False
    if check_password(password or '', usuario.password_hash):
        cache.delete(_clave_fallos(usuario))
        return True
    clave = _clave_fallos(usuario)
    cache.set(clave, cache.get(clave, 0) + 1, settings.CONFIRMACION_BLOQUEO_SEGUNDOS)
    return False
