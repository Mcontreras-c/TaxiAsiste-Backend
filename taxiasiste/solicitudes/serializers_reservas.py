from rest_framework import serializers

from . import reservas_logic
from .models import Reserva


class ReservaCrearSerializer(serializers.Serializer):
    """Entrada de POST /reservas/ (lo que manda la Central)."""

    origen = serializers.CharField(max_length=200)
    fecha_hora_recogida = serializers.DateTimeField()
    pasajero = serializers.IntegerField(required=False, allow_null=True)
    observaciones = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)

    def validate_origen(self, valor):
        valor = valor.strip()
        if not valor:
            raise serializers.ValidationError('La dirección de recogida es obligatoria.')
        return valor


class ReservaSerializer(serializers.ModelSerializer):
    """
    Salida de las reservas. Para el conductor que aun NO la tomo (listado
    "disponibles") se pasa context['ocultar_pasajero']=True: ve donde y cuando,
    pero no quien es el pasajero.
    """

    pasajero_nombre = serializers.SerializerMethodField()
    pasajero_telefono = serializers.SerializerMethodField()
    movil_patente = serializers.SerializerMethodField()
    conductor_nombre = serializers.SerializerMethodField()
    salida_base_maxima = serializers.SerializerMethodField()
    libre_desde = serializers.SerializerMethodField()

    class Meta:
        model = Reserva
        fields = [
            'id_reserva', 'folio', 'estado',
            'origen', 'origen_lat', 'origen_lng', 'destino',
            'fecha_hora_recogida', 'duracion_estimada_s', 'distancia_estimada_m', 'tarifa_estimada',
            'salida_base_maxima', 'libre_desde',
            'pasajero', 'pasajero_nombre', 'pasajero_telefono',
            'movil', 'movil_patente', 'conductor_nombre',
            'observaciones', 'fecha_creacion', 'fecha_tomada', 'fecha_termino',
        ]
        read_only_fields = fields

    def _oculto(self):
        return bool(self.context.get('ocultar_pasajero'))

    def get_pasajero_nombre(self, obj):
        if self._oculto() or not obj.pasajero:
            return None
        return f'{obj.pasajero.nombre} {obj.pasajero.apellido}'

    def get_pasajero_telefono(self, obj):
        if self._oculto() or not obj.pasajero:
            return None
        return obj.pasajero.telefono

    def get_movil_patente(self, obj):
        return obj.movil.patente if obj.movil else None

    def get_conductor_nombre(self, obj):
        if not obj.movil:
            return None
        socio = obj.movil.socio
        return f'{socio.nombre} {socio.apellido}'

    def get_salida_base_maxima(self, obj):
        return reservas_logic.hora_maxima_salida(obj.fecha_hora_recogida, obj.duracion_estimada_s)

    def get_libre_desde(self, obj):
        return reservas_logic.franja(obj.fecha_hora_recogida, obj.duracion_estimada_s)[1]
