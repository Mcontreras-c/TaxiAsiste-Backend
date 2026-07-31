from django.db import models

from taxiasiste.utils.oracle_seq import nextval


class Movil(models.Model):
    id_movil = models.FloatField(primary_key=True)
    socio = models.ForeignKey(
        'socios.Socio',
        models.DO_NOTHING,
        db_column='id_socio',
        related_name='moviles',
    )
    patente = models.CharField(
        unique=True,
        max_length=10,
        db_comment='Formato chileno: ABCD12 o AB1234',
    )
    marca = models.CharField(max_length=50, blank=True, null=True)
    modelo = models.CharField(max_length=50, blank=True, null=True)
    anio = models.SmallIntegerField(blank=True, null=True)
    color = models.CharField(max_length=30, blank=True, null=True)
    estado_operativo = models.CharField(
        max_length=20,
        default='DISPONIBLE',
        db_comment='DISPONIBLE | EN_SERVICIO | BLOQUEADO | INACTIVO',
    )
    fecha_registro = models.DateField()

    class Meta:
        managed = False
        db_table = 'MOVILES'
        db_table_comment = 'Vehículos del sindicato'

    def save(self, *args, **kwargs):
        if not self.id_movil:
            self.id_movil = nextval('seq_moviles')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.patente} — {self.socio} ({self.estado_operativo})'


class FilaBase(models.Model):
    id_fila = models.FloatField(primary_key=True)
    movil = models.ForeignKey(
        Movil,
        models.DO_NOTHING,
        db_column='id_movil',
        related_name='entradas_fila',
    )
    posicion = models.IntegerField()
    fecha_ingreso = models.DateTimeField()
    fecha_llamado = models.DateTimeField(blank=True, null=True)
    fecha_salida = models.DateTimeField(blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        default='EN_ESPERA',
        db_comment='EN_ESPERA | LLAMADO | RETIRADO',
    )

    class Meta:
        managed = False
        db_table = 'FILA_BASE'
        db_table_comment = 'Cola ordenada de móviles en base — gestionada por el paletero'

    def save(self, *args, **kwargs):
        if not self.id_fila:
            self.id_fila = nextval('seq_fila_base')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Pos {self.posicion} — {self.movil.patente} ({self.estado})'


class UbicacionActual(models.Model):
    id_ubicacion = models.FloatField(primary_key=True)
    movil = models.OneToOneField(
        Movil,
        models.DO_NOTHING,
        db_column='id_movil',
        related_name='ubicacion_actual',
    )
    lat = models.DecimalField(max_digits=10, decimal_places=6)
    lng = models.DecimalField(max_digits=10, decimal_places=6)
    heading = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    velocidad_kmh = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'UBICACION_ACTUAL'
        db_table_comment = 'Ultima posicion GPS conocida de cada movil (no es historial)'

    def save(self, *args, **kwargs):
        if not self.id_ubicacion:
            self.id_ubicacion = nextval('seq_ubicaciones')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.movil.patente} @ ({self.lat}, {self.lng})'
