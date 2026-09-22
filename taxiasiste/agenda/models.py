from django.db import models

from taxiasiste.utils.oracle_seq import nextval


class EventoAgenda(models.Model):
    id_evento_agenda = models.FloatField(primary_key=True)
    titulo = models.CharField(max_length=150)
    descripcion = models.CharField(max_length=1000, blank=True, null=True)
    fecha_hora = models.DateTimeField()
    lugar = models.CharField(max_length=200, blank=True, null=True)
    usuario_creador = models.ForeignKey(
        'usuarios.Usuario',
        models.DO_NOTHING,
        db_column='id_usuario_creador',
        blank=True,
        null=True,
        related_name='eventos_agenda',
    )
    fecha_creacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'EVENTOS_AGENDA'
        db_table_comment = 'Reuniones y fechas importantes de la secretaria'

    def save(self, *args, **kwargs):
        if not self.id_evento_agenda:
            self.id_evento_agenda = nextval('seq_eventos_agenda')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.titulo} — {self.fecha_hora:%Y-%m-%d %H:%M}'


class DocumentoAgenda(models.Model):
    id_documento = models.FloatField(primary_key=True)
    nombre = models.CharField(max_length=200, db_comment='Nombre descriptivo elegido al subirlo, no el nombre del archivo original')
    archivo = models.FileField(upload_to='documentos_agenda/')
    categoria = models.CharField(max_length=50, blank=True, null=True)
    usuario_subio = models.ForeignKey(
        'usuarios.Usuario',
        models.DO_NOTHING,
        db_column='id_usuario_subio',
        blank=True,
        null=True,
        related_name='documentos_agenda',
    )
    fecha_subida = models.DateTimeField(blank=True, null=True)
    tamano_bytes = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'DOCUMENTOS_AGENDA'
        db_table_comment = 'Documentos digitalizados de la secretaria'

    def save(self, *args, **kwargs):
        if not self.id_documento:
            self.id_documento = nextval('seq_documentos_agenda')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre
