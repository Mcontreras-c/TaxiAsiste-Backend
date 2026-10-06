import decimal

from django.utils import timezone
from rest_framework import serializers

from . import fila_logic
from .models import FilaBase, Movil, UbicacionActual


class RoundingDecimalField(serializers.DecimalField):
    """
    DecimalField que redondea ANTES de validar la precision. El DecimalField
    normal de DRF valida max_decimal_places sobre el valor crudo y recien
    despues aplica 'rounding' al cuantizar — por eso el kwarg 'rounding' solo,
    nunca alcanza a evitar el error 'Ensure that there are no more than N
    decimal places' cuando el GPS entrega mas decimales de los que la columna
    la base admite (comun en telefonos reales, que dan 7+ decimales).

    coerce_to_string=False por defecto: DRF serializa DecimalField como
    string por default (para no perder precision en JSON), pero
    react-native-maps rechaza un string en latitude/longitude con
    UnexpectedNativeTypeException — necesita un number de verdad. Leaflet
    (web) toleraba el string por su tipado laxo; react-native-maps no.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('coerce_to_string', False)
        super().__init__(*args, **kwargs)

    def validate_precision(self, value):
        quantizer = decimal.Decimal('1') / (decimal.Decimal(10) ** self.decimal_places)
        value = value.quantize(quantizer, rounding=decimal.ROUND_HALF_UP)
        return super().validate_precision(value)


class MovilSerializer(serializers.ModelSerializer):
    socio_nombre   = serializers.CharField(source='socio.__str__', read_only=True)
    socio_telefono = serializers.CharField(source='socio.telefono', read_only=True)
    lat            = serializers.DecimalField(source='ubicacion_actual.lat', max_digits=10, decimal_places=6, read_only=True, default=None, coerce_to_string=False)
    lng            = serializers.DecimalField(source='ubicacion_actual.lng', max_digits=10, decimal_places=6, read_only=True, default=None, coerce_to_string=False)
    # La columna tiene DEFAULT CURRENT_DATE a nivel de Postgres, pero el
    # modelo es managed=False y Django no lo sabe -- sin esto, DRF exige
    # fecha_registro en el body y "Nuevo socio" (con vehiculo) o "Agregar
    # vehiculo" fallan siempre con un 400 generico ("Error al guardar el
    # vehiculo.") que no dice por que. Mismo bug que ya se corrigio en
    # SocioSerializer.fecha_ingreso.
    fecha_registro = serializers.DateField(required=False, default=timezone.localdate)

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


class FilaBaseSerializer(serializers.ModelSerializer):
    patente = serializers.CharField(source='movil.patente', read_only=True)
    socio_nombre = serializers.CharField(source='movil.socio.__str__', read_only=True)
    # Llamado con "Voy": el servidor calcula el tiempo que queda, asi la cuenta regresiva
    # de la app coincide con la del servidor aunque el reloj del telefono este desfasado.
    confirmado = serializers.SerializerMethodField()
    llamado_vence_en = serializers.SerializerMethodField()
    segundos_restantes = serializers.SerializerMethodField()

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
            'confirmado',
            'confirmado_en',
            'no_respuestas',
            'motivo_salida',
            'llamado_vence_en',
            'segundos_restantes',
        ]
        read_only_fields = [
            'id_fila', 'posicion', 'fecha_ingreso', 'confirmado_en', 'no_respuestas', 'motivo_salida',
        ]

    def get_confirmado(self, obj):
        return obj.confirmado_en is not None

    def get_llamado_vence_en(self, obj):
        vence = fila_logic.vence_llamado(obj)
        return vence.isoformat() if vence else None

    def get_segundos_restantes(self, obj):
        return fila_logic.segundos_restantes(obj)


class UbicacionActualSerializer(serializers.ModelSerializer):
    # El GPS de un telefono real suele entregar mas de 6 decimales; en vez de
    # rechazar la request, se redondea al mismo formato que la columna de la base
    # (NUMBER(10,6)) — 'rounding' hace que DecimalField cuantice en lugar de
    # lanzar 'Ensure that there are no more than N decimal places'.
    lat = RoundingDecimalField(max_digits=10, decimal_places=6)
    lng = RoundingDecimalField(max_digits=10, decimal_places=6)
    heading = RoundingDecimalField(max_digits=5, decimal_places=1, required=False, allow_null=True)
    velocidad_kmh = RoundingDecimalField(max_digits=5, decimal_places=1, required=False, allow_null=True)
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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        usuario = getattr(request, 'user', None)
        rol = getattr(getattr(usuario, 'rol', None), 'nombre_rol', None)
        if rol == 'Conductor':
            # Un conductor ve a los demas solo por nombre: ni patente ni RUT
            # (el __str__ del socio incluye el RUT entre parentesis). Su propio
            # movil se entrega completo.
            propio = instance.movil.socio.usuario_id == usuario.id_usuario
            if not propio:
                socio = instance.movil.socio
                data['patente'] = ''
                data['socio_nombre'] = f'{socio.nombre} {socio.apellido}'
        return data
