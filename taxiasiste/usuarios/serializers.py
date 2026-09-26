import re

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .emails import enviar_credenciales_iniciales
from .models import Rol, Usuario
from .passwords import generar_clave


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ['id_rol', 'nombre_rol', 'descripcion', 'activo']


class UsuarioSerializer(serializers.ModelSerializer):
    rol = RolSerializer(read_only=True)
    id_rol = serializers.PrimaryKeyRelatedField(
        queryset=Rol.objects.all(),
        source='rol',
        write_only=True,
    )
    nombre_completo = serializers.SerializerMethodField()
    # id_socio: solo al crear un Conductor -- vincula el usuario nuevo a un
    # socio existente sin login todavia (ver validate_id_socio/create()).
    # La contrasena NUNCA la manda el cliente: el servidor la genera, la
    # envia por correo (enviar_credenciales_iniciales) y no vuelve en la
    # respuesta -- por eso no hay campo 'password' aca.
    id_socio = serializers.IntegerField(
        write_only=True, required=False, allow_null=True,
        help_text='Si el rol es Conductor, vincula el usuario nuevo a este socio '
                   '(debe existir y no tener usuario todavia).',
    )

    class Meta:
        model = Usuario
        fields = [
            'id_usuario',
            'rol',
            'id_rol',
            'username',
            'email',
            'nombre',
            'apellido',
            'nombre_completo',
            'estado',
            'fecha_creacion',
            'ultimo_acceso',
            'id_socio',
        ]
        read_only_fields = ['id_usuario', 'fecha_creacion', 'ultimo_acceso']

    def get_nombre_completo(self, obj):
        """
        Un Conductor no tiene nombre propio en USUARIOS -- se muestra el de
        su Socio vinculado. El resto de los roles (personal del sindicato)
        usa nombre/apellido de este mismo registro.
        """
        from taxiasiste.socios.models import Socio

        try:
            socio = obj.socio
        except Socio.DoesNotExist:
            socio = None

        if socio:
            return f'{socio.nombre} {socio.apellido}'
        if obj.nombre or obj.apellido:
            return f'{obj.nombre or ""} {obj.apellido or ""}'.strip()
        return obj.username

    def validate(self, attrs):
        # El correo es el UNICO canal de entrega de la clave generada -- sin
        # el, la cuenta quedaria creada sin forma de comunicar el acceso.
        if self.instance is None and not attrs.get('email'):
            raise serializers.ValidationError({'email': 'El correo es requerido para poder enviar la contraseña.'})
        return attrs

    def validate_id_socio(self, value):
        if value is None:
            return value
        from taxiasiste.socios.models import Socio

        if not Socio.objects.filter(pk=value, usuario__isnull=True).exists():
            raise serializers.ValidationError('Ese socio no existe o ya tiene un usuario.')
        return value

    @transaction.atomic
    def create(self, validated_data):
        from taxiasiste.socios.models import Socio

        id_socio = validated_data.pop('id_socio', None)
        clave = generar_clave()
        validated_data['password_hash'] = make_password(clave)
        validated_data.setdefault('fecha_creacion', timezone.localdate())

        usuario = Usuario.objects.create(**validated_data)

        if id_socio:
            # Revalidado (no solo confiar en validate_id_socio): entre la
            # validacion y este punto no hay lock, otra request pudo haber
            # tomado el mismo socio -- mejor abortar la transaccion completa
            # (usuario incluido) que dejar dos usuarios apuntando, sin
            # querer, al mismo socio.
            actualizado = Socio.objects.filter(pk=id_socio, usuario__isnull=True).update(usuario=usuario)
            if not actualizado:
                raise serializers.ValidationError({'id_socio': 'Ese socio ya no está disponible.'})

        enviar_credenciales_iniciales(usuario, clave)
        return usuario


class PerfilSerializer(serializers.Serializer):
    """Lo que la persona ve de su propia cuenta (GET /usuarios/mi_perfil/)."""

    id_usuario = serializers.IntegerField()
    username = serializers.CharField()
    rol = serializers.SerializerMethodField()
    nombre = serializers.SerializerMethodField()
    apellido = serializers.SerializerMethodField()
    nombre_completo = serializers.SerializerMethodField()
    rut = serializers.SerializerMethodField()
    email = serializers.CharField(allow_null=True)
    telefono = serializers.SerializerMethodField()
    es_socio = serializers.SerializerMethodField()

    @staticmethod
    def socio_de(obj):
        """Socio vinculado al usuario, o None si es personal sin ficha de socio."""
        from taxiasiste.socios.models import Socio

        try:
            return obj.socio
        except Socio.DoesNotExist:
            return None

    def get_rol(self, obj):
        return obj.rol.nombre_rol

    def get_nombre(self, obj):
        socio = self.socio_de(obj)
        return socio.nombre if socio else obj.nombre

    def get_apellido(self, obj):
        socio = self.socio_de(obj)
        return socio.apellido if socio else obj.apellido

    def get_nombre_completo(self, obj):
        return ' '.join(x for x in (self.get_nombre(obj), self.get_apellido(obj)) if x) or obj.username

    def get_rut(self, obj):
        socio = self.socio_de(obj)
        return socio.rut if socio else None

    def get_telefono(self, obj):
        socio = self.socio_de(obj)
        return socio.telefono if socio else obj.telefono

    def get_es_socio(self, obj):
        return self.socio_de(obj) is not None


TELEFONO_RE = re.compile(r'^\+?\d{8,15}$')


def normalizar_telefono(valor):
    """
    Quita espacios, guiones y parentesis y valida que queden solo digitos (con
    un + opcional al inicio), entre 8 y 15. Devuelve None si viene vacio.
    """
    limpio = re.sub(r'[\s\-()]', '', valor or '')
    if not limpio:
        return None
    if not TELEFONO_RE.match(limpio):
        raise serializers.ValidationError('Teléfono inválido: usa solo números (ej. +56 9 1234 5678).')
    return limpio


class PerfilEditarSerializer(serializers.Serializer):
    """Entrada de PATCH /usuarios/mi_perfil/: solo lo que la persona puede cambiar de si misma."""

    email = serializers.EmailField(max_length=100, required=False)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    # Cambiar el correo (que sirve para recuperar la clave) exige la clave actual.
    password_actual = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate_telefono(self, valor):
        return normalizar_telefono(valor)
