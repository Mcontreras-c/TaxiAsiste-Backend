from rest_framework import serializers

from .models import Bloqueo, Cuota, Socio


class SocioSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.SerializerMethodField()

    class Meta:
        model = Socio
        fields = [
            'id_socio',
            'usuario',
            'rut',
            'nombre',
            'apellido',
            'nombre_completo',
            'telefono',
            'direccion',
            'estado_socio',
            'fecha_ingreso',
            'fecha_egreso',
        ]
        read_only_fields = ['id_socio']

    def get_nombre_completo(self, obj):
        return f'{obj.nombre} {obj.apellido}'


class CuotaSerializer(serializers.ModelSerializer):
    socio_nombre = serializers.CharField(source='socio.__str__', read_only=True)

    class Meta:
        model = Cuota
        fields = [
            'id_cuota',
            'socio',
            'socio_nombre',
            'periodo',
            'monto',
            'estado_pago',
            'fecha_vencimiento',
            'fecha_pago',
            'observacion',
        ]
        read_only_fields = ['id_cuota']


class BloqueoSerializer(serializers.ModelSerializer):
    socio_nombre = serializers.CharField(source='socio.__str__', read_only=True)
    activo = serializers.IntegerField(default=1)

    class Meta:
        model = Bloqueo
        fields = [
            'id_bloqueo',
            'socio',
            'socio_nombre',
            'usuario_registra',
            'motivo',
            'tipo_bloqueo',
            'fecha_inicio',
            'fecha_fin',
            'activo',
        ]
        read_only_fields = ['id_bloqueo']
