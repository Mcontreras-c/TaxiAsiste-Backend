from django.db import models
from django.utils import timezone

from taxiasiste.utils.oracle_seq import nextval


class HistorialEvento(models.Model):
    id_evento = models.FloatField(primary_key=True)
    usuario = models.ForeignKey(
        'usuarios.Usuario',
        models.DO_NOTHING,
        db_column='id_usuario',
        blank=True,
        null=True,
        related_name='eventos',
    )
    entidad_tipo = models.CharField(
        max_length=30,
        db_comment='SOLICITUD | BLOQUEO | CUOTA | MOVIL | SOCIO | USUARIO | PASAJERO | FILA_BASE',
    )
    entidad_id = models.FloatField(db_comment='ID del registro afectado')
    evento = models.CharField(max_length=100)
    estado_anterior = models.CharField(max_length=50, blank=True, null=True)
    estado_nuevo = models.CharField(max_length=50, blank=True, null=True)
    detalle = models.CharField(max_length=500, blank=True, null=True)
    ip_origen = models.CharField(max_length=45, blank=True, null=True)
    fecha_hora = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'HISTORIAL_EVENTOS'
        db_table_comment = 'Trazabilidad genérica del sistema'

    def save(self, *args, **kwargs):
        if not self.id_evento:
            self.id_evento = nextval('seq_historial')
        if not self.fecha_hora:
            self.fecha_hora = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.fecha_hora:%Y-%m-%d %H:%M} | {self.entidad_tipo}#{self.entidad_id} | {self.evento}'
