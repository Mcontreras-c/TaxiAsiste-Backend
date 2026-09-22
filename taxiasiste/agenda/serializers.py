from django.utils import timezone
from rest_framework import serializers

from .models import DocumentoAgenda, EventoAgenda


class EventoAgendaSerializer(serializers.ModelSerializer):
    usuario_creador_nombre = serializers.CharField(source='usuario_creador.username', read_only=True)
    fecha_creacion = serializers.DateTimeField(required=False, default=timezone.now)

    class Meta:
        model = EventoAgenda
        fields = [
            'id_evento_agenda',
            'titulo',
            'descripcion',
            'fecha_hora',
            'lugar',
            'usuario_creador',
            'usuario_creador_nombre',
            'fecha_creacion',
        ]
        read_only_fields = ['id_evento_agenda']


class DocumentoAgendaSerializer(serializers.ModelSerializer):
    usuario_subio_nombre = serializers.CharField(source='usuario_subio.username', read_only=True)
    fecha_subida = serializers.DateTimeField(required=False, default=timezone.now)
    tamano_bytes = serializers.IntegerField(required=False)

    class Meta:
        model = DocumentoAgenda
        fields = [
            'id_documento',
            'nombre',
            'archivo',
            'categoria',
            'usuario_subio',
            'usuario_subio_nombre',
            'fecha_subida',
            'tamano_bytes',
        ]
        read_only_fields = ['id_documento']

    def create(self, validated_data):
        archivo = validated_data.get('archivo')
        if archivo is not None:
            validated_data['tamano_bytes'] = archivo.size
        return super().create(validated_data)
