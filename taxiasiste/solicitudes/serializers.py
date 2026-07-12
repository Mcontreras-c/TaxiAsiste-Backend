from rest_framework import serializers

from .models import Pasajero, Solicitud


class PasajeroSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.SerializerMethodField()

    class Meta:
        model = Pasajero
        fields = [
            'id_pasajero',
            'rut',
            'nombre',
            'apellido',
            'nombre_completo',
            'telefono',
            'direccion_frecuente',
            'fecha_registro',
            'activo',
        ]
        read_only_fields = ['id_pasajero']

    def get_nombre_completo(self, obj):
        return f'{obj.nombre} {obj.apellido}'


class SolicitudListSerializer(serializers.ModelSerializer):
    """Serializer liviano para listados — evita queries pesadas."""
    pasajero_nombre = serializers.CharField(source='pasajero.__str__', read_only=True)
    movil_patente = serializers.CharField(source='movil.patente', read_only=True)

    class Meta:
        model = Solicitud
        fields = [
            'id_solicitud',
            'folio',
            'tipo_solicitud',
            'estado',
            'canal_entrada',
            'pasajero_nombre',
            'movil_patente',
            'origen',
            'destino',
            'fecha_hora_registro',
            'fecha_programada',
        ]
        read_only_fields = ['id_solicitud']


class SolicitudSerializer(serializers.ModelSerializer):
    """Serializer completo para crear, editar y ver detalle."""
    pasajero_nombre = serializers.CharField(source='pasajero.__str__', read_only=True)
    movil_patente = serializers.CharField(source='movil.patente', read_only=True)

    class Meta:
        model = Solicitud
        fields = [
            'id_solicitud',
            'folio',
            'tipo_solicitud',
            'pasajero',
            'pasajero_nombre',
            'movil',
            'movil_patente',
            'usuario_central',
            'origen',
            'destino',
            'fecha_hora_registro',
            'fecha_programada',
            'estado',
            'canal_entrada',
            'intentos_asignacion',
            'observaciones',
            'fecha_asignacion',
            'fecha_inicio',
            'fecha_termino',
            'motivo_cancelacion',
        ]
        read_only_fields = ['id_solicitud', 'intentos_asignacion']
