from django.utils import timezone
from rest_framework import serializers

from .models import EventoAgenda


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
