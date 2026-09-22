from django.utils import timezone
from rest_framework import serializers

from .models import Bloqueo, Cuota, Socio, TesoreriaMovimiento


class SocioSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.SerializerMethodField()
    cuotas_vencidas = serializers.SerializerMethodField()
    # La columna tiene DEFAULT CURRENT_DATE a nivel de Postgres, pero el
    # modelo es managed=False y Django no lo sabe -- sin esto, DRF exige
    # fecha_ingreso en el body y "Nuevo socio" fallaba siempre con un 400
    # generico ("Error al guardar.") que no decia por que.
    fecha_ingreso = serializers.DateField(required=False, default=timezone.localdate)

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
            'cuotas_vencidas',
        ]
        read_only_fields = ['id_socio']

    def get_nombre_completo(self, obj):
        return f'{obj.nombre} {obj.apellido}'

    def get_cuotas_vencidas(self, obj):
        hoy = timezone.now().date()
        return obj.cuotas.filter(
            estado_pago__in=['PENDIENTE', 'VENCIDO'],
            fecha_vencimiento__lt=hoy,
        ).count()


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


class TesoreriaMovimientoSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario_registra.username', read_only=True)

    class Meta:
        model = TesoreriaMovimiento
        fields = [
            'id_movimiento',
            'usuario_registra',
            'usuario_nombre',
            'cuota',
            'tipo',
            'categoria',
            'descripcion',
            'monto',
            'fecha',
        ]
        read_only_fields = ['id_movimiento']
