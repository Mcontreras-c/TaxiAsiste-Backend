from django.db import models
from django.utils import timezone

from taxiasiste.utils.oracle_seq import nextval

DESTINO_UNICO = 'Hospital Félix Bulnes, Cerro Navia'


class Pasajero(models.Model):
    id_pasajero = models.FloatField(primary_key=True)
    rut = models.CharField(unique=True, max_length=12)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion_frecuente = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        db_comment='Domicilio habitual para autocompletar el origen',
    )
    fecha_registro = models.DateField()
    activo = models.SmallIntegerField(
        default=1,
        db_comment='1=activo, 0=inactivo',
    )

    class Meta:
        managed = False
        db_table = 'PASAJEROS'
        db_table_comment = 'Pasajeros frecuentes — autocompletar por RUT en la central'

    def save(self, *args, **kwargs):
        if not self.id_pasajero:
            self.id_pasajero = nextval('seq_pasajeros')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.nombre} {self.apellido} ({self.rut})'


class Solicitud(models.Model):
    id_solicitud = models.FloatField(primary_key=True)
    pasajero = models.ForeignKey(
        Pasajero,
        models.DO_NOTHING,
        db_column='id_pasajero',
        blank=True,
        null=True,
        related_name='solicitudes',
    )
    movil = models.ForeignKey(
        'moviles.Movil',
        models.DO_NOTHING,
        db_column='id_movil',
        blank=True,
        null=True,
        related_name='solicitudes',
    )
    usuario_central = models.ForeignKey(
        'usuarios.Usuario',
        models.DO_NOTHING,
        db_column='id_usuario_central',
        blank=True,
        null=True,
        related_name='solicitudes_gestionadas',
    )
    folio = models.CharField(
        unique=True,
        max_length=20,
        db_comment='Código legible — ej: SOL-2026-00001',
    )
    origen = models.CharField(max_length=200)
    origen_lat = models.DecimalField(
        max_digits=10, decimal_places=6, blank=True, null=True,
        db_comment='Geocodificado desde origen al crear la solicitud (best-effort, puede quedar null)',
    )
    origen_lng = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    destino = models.CharField(max_length=200)
    fecha_hora = models.DateTimeField(
        db_comment='Momento en que la central registra la solicitud',
    )
    estado = models.CharField(
        max_length=20,
        default='PENDIENTE',
        db_comment='PENDIENTE | ASIGNADO | EN_CURSO | COMPLETADO | CANCELADO',
    )
    canal_entrada = models.CharField(
        max_length=20,
        default='TELEFONO',
        db_comment='TELEFONO | APP | PRESENCIAL',
    )
    observaciones = models.CharField(max_length=500, blank=True, null=True)
    fecha_asignacion = models.DateTimeField(blank=True, null=True)
    fecha_inicio = models.DateTimeField(blank=True, null=True)
    fecha_termino = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'SOLICITUDES'
        db_table_comment = 'Solicitudes de servicio gestionadas por la central'

    def save(self, *args, **kwargs):
        if not self.id_solicitud:
            self.id_solicitud = nextval('seq_solicitudes')
        # TaxiAsiste solo hace traslados a este hospital -- el destino nunca
        # es libre, se fija siempre aca sin importar lo que mande el cliente.
        self.destino = DESTINO_UNICO
        if not self.folio:
            anio = timezone.now().year
            self.folio = f'SOL-{anio}-{int(self.id_solicitud):05d}'
        if not self.fecha_hora:
            self.fecha_hora = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.folio} ({self.estado})'
