from django.db import models


class Movil(models.Model):
    id_movil = models.FloatField(primary_key=True)
    socio = models.ForeignKey(
        'usuarios.Socio',
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
    anio = models.IntegerField(blank=True, null=True)
    color = models.CharField(max_length=30, blank=True, null=True)
    estado_operativo = models.CharField(
        max_length=20,
        db_comment='DISPONIBLE | EN_SERVICIO | BLOQUEADO | INACTIVO',
    )
    fecha_registro = models.DateField()

    class Meta:
        managed = False
        db_table = 'moviles'
        db_table_comment = 'Vehículos del sindicato'

    def __str__(self):
        return self.patente
