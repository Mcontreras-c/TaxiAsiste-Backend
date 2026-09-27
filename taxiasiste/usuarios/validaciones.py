import re

from rest_framework import serializers

# Dominios de ejemplo/prueba: no reciben correo real, asi que una cuenta creada con
# uno de ellos quedaria sin forma de entregar las credenciales.
DOMINIOS_NO_REALES = {
    'example.com', 'example.org', 'example.net', 'example.cl', 'ejemplo.cl', 'ejemplo.com',
    'test.com', 'test.cl', 'prueba.cl', 'correo.test', 'mail.com.invalid',
}
PATENTE_RE = re.compile(r'^([A-Z]{2}\d{4}|[A-Z]{4}\d{2})$')


def es_correo_real(email):
    dominio = (email or '').rsplit('@', 1)[-1].lower()
    return bool(dominio) and dominio not in DOMINIOS_NO_REALES and not dominio.endswith(('.test', '.invalid', '.example', '.local'))


def validar_correo_real(email, excluir_pk=None):
    """Correo con dominio real y que no use otra cuenta (sin distinguir mayusculas)."""
    from .models import Usuario

    if not es_correo_real(email):
        raise serializers.ValidationError('Ingresa un correo real: ahí se envían las credenciales.')
    usados = Usuario.objects.filter(email__iexact=email)
    if excluir_pk is not None:
        usados = usados.exclude(pk=excluir_pk)
    if usados.exists():
        raise serializers.ValidationError('Ese correo ya está en uso por otra cuenta.')
    return email.strip().lower()


def _digito_verificador(cuerpo):
    suma, factor = 0, 2
    for c in reversed(cuerpo):
        suma += int(c) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return {11: '0', 10: 'K'}.get(resto, str(resto))


def normalizar_rut(valor):
    """'12.345.678-5' / '123456785' -> '12345678-5'. Valida el digito verificador (modulo 11)."""
    limpio = re.sub(r'[.\s-]', '', valor or '').upper()
    if not re.fullmatch(r'\d{7,8}[\dK]', limpio):
        raise serializers.ValidationError('RUT inválido.')
    cuerpo, dv = limpio[:-1], limpio[-1]
    if _digito_verificador(cuerpo) != dv:
        raise serializers.ValidationError('RUT inválido: el dígito verificador no coincide.')
    return f'{cuerpo}-{dv}'


def normalizar_patente(valor):
    limpio = re.sub(r'[\s-]', '', valor or '').upper()
    if not PATENTE_RE.match(limpio):
        raise serializers.ValidationError('Patente inválida (ej. ABCD12 o AB1234).')
    return limpio
