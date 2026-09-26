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
            'incumplimientos',
            'bloqueado_domicilio',
        ]
        # El bloqueo lo maneja el sistema (3 incumplimientos) y un administrador (levantarlo).
        read_only_fields = ['id_pasajero', 'incumplimientos', 'bloqueado_domicilio']

    def get_nombre_completo(self, obj):
        return f'{obj.nombre} {obj.apellido}'


class SolicitudListSerializer(serializers.ModelSerializer):
    """Serializer liviano para listados — evita queries pesadas."""
    pasajero_nombre = serializers.SerializerMethodField()
    pasajero_telefono = serializers.CharField(source='pasajero.telefono', read_only=True)
    movil_patente = serializers.SerializerMethodField()

    class Meta:
        model = Solicitud
        fields = [
            'id_solicitud',
            'folio',
            'estado',
            'canal_entrada',
            'pasajero_nombre',
            'pasajero_telefono',
            'movil_patente',
            'origen',
            'destino',
            'fecha_hora',
        ]

    def get_pasajero_nombre(self, obj):
        return str(obj.pasajero) if obj.pasajero else None

    def get_movil_patente(self, obj):
        return obj.movil.patente if obj.movil else None
        read_only_fields = ['id_solicitud']


class SolicitudSerializer(serializers.ModelSerializer):
    """Serializer completo para crear, editar y ver detalle."""
    pasajero_nombre = serializers.SerializerMethodField()
    movil_patente = serializers.SerializerMethodField()

    class Meta:
        model = Solicitud
        fields = [
            'id_solicitud',
            'folio',
            'pasajero',
            'pasajero_nombre',
            'movil',
            'movil_patente',
            'usuario_central',
            'origen',
            'destino',
            'fecha_hora',
            'estado',
            'canal_entrada',
            'observaciones',
            'fecha_asignacion',
            'fecha_inicio',
            'fecha_termino',
        ]
        read_only_fields = ['id_solicitud', 'folio', 'fecha_hora', 'destino']

    def get_pasajero_nombre(self, obj):
        return str(obj.pasajero) if obj.pasajero else None

    def get_movil_patente(self, obj):
        return obj.movil.patente if obj.movil else None
