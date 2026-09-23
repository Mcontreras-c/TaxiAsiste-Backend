import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def enviar_credenciales_iniciales(usuario, password):
    """
    Correo de bienvenida al crear una cuenta nueva. La contrasena la genera
    el servidor y NUNCA se muestra en la interfaz -- este correo es el unico
    lugar donde existe en texto plano.
    """
    if not usuario.email:
        logger.warning('Usuario %s creado sin email -- no se pudo enviar la clave.', usuario.username)
        return

    rol = usuario.rol.nombre_rol
    cuerpo = (
        f'Hola,\n\n'
        f'Se creo tu cuenta en TaxiAsiste con el rol "{rol}".\n\n'
        f'Usuario: {usuario.username}\n'
        f'Contraseña: {password}\n\n'
        'Te recomendamos cambiarla apenas ingreses.\n\n'
    )
    if settings.APK_DOWNLOAD_URL:
        cuerpo += f'Descarga la app aqui: {settings.APK_DOWNLOAD_URL}\n\n'
    cuerpo += 'Saludos,\nTaxiAsiste'

    try:
        send_mail(
            subject='Bienvenido a TaxiAsiste',
            message=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[usuario.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception('No se pudo enviar las credenciales iniciales a %s', usuario.email)


def enviar_clave_temporal(usuario, clave_temporal):
    """Correo de recuperacion de clave: incluye la clave temporal generada."""
    cuerpo = (
        f'Hola {usuario.username},\n\n'
        f'Tu clave temporal es: {clave_temporal}\n\n'
        'Usala para ingresar y cambiala de inmediato desde tu perfil.\n\n'
        'Si no solicitaste esto, avisa a un administrador.\n\n'
        'Saludos,\nTaxiAsiste'
    )

    try:
        send_mail(
            subject='Recuperacion de contrasena — TaxiAsiste',
            message=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[usuario.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception('No se pudo enviar la clave temporal a %s', usuario.email)
