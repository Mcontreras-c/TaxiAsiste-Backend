from rest_framework import serializers

from .models import FilaBase, Movil


class MovilSerializer(serializers.ModelSerializer):
    socio_nombre   = serializers.CharField(source='socio.__str__', read_only=True)
    socio_telefono = serializers.CharField(source='socio.telefono', read_only=True)

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
        ]
        read_only_fields = ['id_movil']


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
        read_only_fields = ['id_fila', 'posicion']
