from django.db import models


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
        db_comment='Tabla afectada: SOLICITUD, BLOQUEO, CUOTA, etc.',
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
        db_table = 'historial_eventos'
        db_table_comment = 'Trazabilidad genérica del sistema'

    def __str__(self):
        return f'{self.evento} – {self.entidad_tipo}#{self.entidad_id}'
