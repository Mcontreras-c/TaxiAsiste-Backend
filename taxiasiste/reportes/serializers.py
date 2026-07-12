from rest_framework import serializers

from .models import HistorialEvento


class HistorialEventoSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.__str__', read_only=True)

    class Meta:
        model = HistorialEvento
        fields = [
            'id_evento',
            'usuario',
            'usuario_nombre',
            'entidad_tipo',
            'entidad_id',
            'evento',
            'estado_anterior',
            'estado_nuevo',
            'detalle',
            'ip_origen',
            'fecha_hora',
        ]
        read_only_fields = [
            'id_evento',
            'usuario',
            'usuario_nombre',
            'entidad_tipo',
            'entidad_id',
            'evento',
            'estado_anterior',
            'estado_nuevo',
            'detalle',
            'ip_origen',
            'fecha_hora',
        ]
