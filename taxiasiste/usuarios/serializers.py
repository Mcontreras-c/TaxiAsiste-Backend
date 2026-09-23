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
