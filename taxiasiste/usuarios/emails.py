import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

# Roles que usan la app del celular; el resto es personal del panel web.
ROLES_APP_MOVIL = ('Conductor', 'Paletero')


def _enviar(asunto, cuerpo, destinatario):
    """Envia el correo. Devuelve True si salio bien, False si fallo (se registra, no se propaga)."""
    try:
        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destinatario],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception('No se pudo enviar correo a %s', destinatario)
        return False


def _cuerpo_credenciales(usuario, password, intro):
    rol = usuario.rol.nombre_rol
    cuerpo = (
        f'Hola,\n\n'
        f'{intro} con el rol "{rol}".\n\n'
        f'Usuario: {usuario.username}\n'
        f'Contraseña: {password}\n\n'
    )

    if rol in ROLES_APP_MOVIL:
        cuerpo += 'Como ingresar con tu cuenta:\n'
        if settings.APK_DOWNLOAD_URL:
            cuerpo += (
                f'1. Descarga la app desde el celular: {settings.APK_DOWNLOAD_URL}\n'
                '2. Si ya tenias una version anterior de la app y no se actualiza, '
                'desinstalala antes de instalar esta.\n'
                '3. Abre la app e ingresa con tu usuario y contraseña.\n'
            )
        else:
            cuerpo += '1. Abre la app de TaxiAsiste e ingresa con tu usuario y contraseña.\n'
        cuerpo += '\nCambia la contraseña provisoria apenas ingreses, desde el menu de la app.\n\n'
    else:
        if settings.PANEL_WEB_URL:
            cuerpo += f'Ingresa al panel web: {settings.PANEL_WEB_URL}\n\n'
        cuerpo += 'Cambia la contraseña provisoria apenas ingreses, con el icono de la llave del menu lateral.\n\n'

    cuerpo += 'Saludos,\nTaxiAsiste'
    return cuerpo


def enviar_credenciales_iniciales(usuario, password):
    """
    Correo de bienvenida al crear una cuenta nueva. La contrasena la genera
    el servidor y NUNCA se muestra en la interfaz -- este correo es el unico
    lugar donde existe en texto plano. Devuelve True si se envio.
    """
    if not usuario.email:
        logger.warning('Usuario %s creado sin email -- no se pudo enviar la clave.', usuario.username)
        return False
    return _enviar(
        'Bienvenido a TaxiAsiste',
        _cuerpo_credenciales(usuario, password, 'Se creo tu cuenta en TaxiAsiste'),
        usuario.email,
    )


def enviar_credenciales_reenviadas(usuario, password):
    """Mismo contenido, pero para una cuenta que ya existia (el admin genero una clave nueva)."""
    if not usuario.email:
        return False
    return _enviar(
        'Tus credenciales de TaxiAsiste',
        _cuerpo_credenciales(usuario, password, 'Te enviamos tus credenciales de acceso a TaxiAsiste'),
        usuario.email,
    )


def enviar_clave_temporal(usuario, clave_temporal):
    """Correo de recuperacion de clave: incluye la clave temporal generada."""
    cuerpo = (
        f'Hola {usuario.username},\n\n'
        f'Tu clave temporal es: {clave_temporal}\n\n'
        'Usala para ingresar y cambiala de inmediato desde tu perfil.\n\n'
        'Si no solicitaste esto, avisa a un administrador.\n\n'
        'Saludos,\nTaxiAsiste'
    )
    return _enviar('Recuperacion de contrasena — TaxiAsiste', cuerpo, usuario.email)


def enviar_aviso_cambio_correo(usuario, correo_anterior, correo_nuevo):
    """
    Aviso al correo ANTERIOR cuando alguien cambia el correo de su cuenta: el
    correo se usa para recuperar la clave, asi que si un tercero lo cambia, el
    dueño original se entera y puede avisar a un administrador.
    """
    cuerpo = (
        f'Hola {usuario.username},\n\n'
        f'El correo de tu cuenta de TaxiAsiste se cambio a: {correo_nuevo}\n\n'
        'Si fuiste tu, no tienes que hacer nada. Si no reconoces este cambio, '
        'avisa de inmediato a un administrador.\n\n'
        'Saludos,\nTaxiAsiste'
    )
    return _enviar('Cambio de correo en tu cuenta — TaxiAsiste', cuerpo, correo_anterior)
