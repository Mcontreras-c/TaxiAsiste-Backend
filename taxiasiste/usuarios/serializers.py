from rest_framework import serializers

from .models import Rol, Usuario


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

    class Meta:
        model = Usuario
        fields = [
            'id_usuario',
            'rol',
            'id_rol',
            'username',
            'email',
            'estado',
            'fecha_creacion',
            'ultimo_acceso',
        ]
        read_only_fields = ['id_usuario', 'fecha_creacion', 'ultimo_acceso']
