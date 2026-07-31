import decimal

from rest_framework import serializers

from .models import FilaBase, Movil, UbicacionActual


class RoundingDecimalField(serializers.DecimalField):
    """
    DecimalField que redondea ANTES de validar la precision. El DecimalField
    normal de DRF valida max_decimal_places sobre el valor crudo y recien
    despues aplica 'rounding' al cuantizar — por eso el kwarg 'rounding' solo,
    nunca alcanza a evitar el error 'Ensure that there are no more than N
    decimal places' cuando el GPS entrega mas decimales de los que la columna
    Oracle admite (comun en telefonos reales, que dan 7+ decimales).
    """

    def validate_precision(self, value):
        quantizer = decimal.Decimal('1') / (decimal.Decimal(10) ** self.decimal_places)
        value = value.quantize(quantizer, rounding=decimal.ROUND_HALF_UP)
        return super().validate_precision(value)


class MovilSerializer(serializers.ModelSerializer):
    socio_nombre   = serializers.CharField(source='socio.__str__', read_only=True)
    socio_telefono = serializers.CharField(source='socio.telefono', read_only=True)
    lat            = serializers.DecimalField(source='ubicacion_actual.lat', max_digits=10, decimal_places=6, read_only=True, default=None)
    lng            = serializers.DecimalField(source='ubicacion_actual.lng', max_digits=10, decimal_places=6, read_only=True, default=None)

    class Meta:
        model = Movil
        fields = [
            'id_movil',
            'socio',
            'socio_nombre',
            'socio_telefono',
            'patente',
            'marca',
            'modelo',
            'anio',
            'color',
            'estado_operativo',
            'fecha_registro',
            'lat',
            'lng',
        ]
        read_only_fields = ['id_movil']

    def to_representation(self, instance):
        # ubicacion_actual puede no existir aun (movil sin GPS reportado todavia)
        try:
            instance.ubicacion_actual
        except UbicacionActual.DoesNotExist:
            data = super().to_representation(instance)
            data['lat'] = None
            data['lng'] = None
            return data
        return super().to_representation(instance)


class UbicacionActualSerializer(serializers.ModelSerializer):
    # El GPS de un telefono real suele entregar mas de 6 decimales; en vez de
    # rechazar la request, se redondea al mismo formato que la columna Oracle
    # (NUMBER(10,6)) — 'rounding' hace que DecimalField cuantice en lugar de
    # lanzar 'Ensure that there are no more than N decimal places'.
    lat = RoundingDecimalField(max_digits=10, decimal_places=6)
    lng = RoundingDecimalField(max_digits=10, decimal_places=6)
    heading = RoundingDecimalField(max_digits=5, decimal_places=1, required=False, allow_null=True)
    velocidad_kmh = RoundingDecimalField(max_digits=5, decimal_places=1, required=False, allow_null=True)

    class Meta:
        model = UbicacionActual
        fields = ['lat', 'lng', 'heading', 'velocidad_kmh', 'actualizado_en']
        read_only_fields = ['actualizado_en']


class FilaBaseSerializer(serializers.ModelSerializer):
    patente = serializers.CharField(source='movil.patente', read_only=True)
    socio_nombre = serializers.CharField(source='movil.socio.__str__', read_only=True)

    class Meta:
        model = FilaBase
        fields = [
            'id_fila',
            'movil',
            'patente',
            'socio_nombre',
            'posicion',
            'fecha_ingreso',
            'fecha_llamado',
            'fecha_salida',
            'estado',
        ]
        read_only_fields = ['id_fila', 'posicion', 'fecha_ingreso']


class UbicacionActualSerializer(serializers.ModelSerializer):
    patente = serializers.CharField(source='movil.patente', read_only=True)
    socio_nombre = serializers.CharField(source='movil.socio.__str__', read_only=True)

    class Meta:
        model = UbicacionActual
        fields = [
            'id_ubicacion',
            'movil',
            'patente',
            'socio_nombre',
            'lat',
            'lng',
            'heading',
            'velocidad_kmh',
            'actualizado_en',
        ]
        read_only_fields = ['id_ubicacion', 'movil', 'actualizado_en']
