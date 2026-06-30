from django.db import models


class Solicitud(models.Model):
    id_solicitud = models.FloatField(primary_key=True)
    pasajero = models.ForeignKey(
        'usuarios.Pasajero',
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
        db_comment='Código legible – ej: SOL-2026-00001',
    )
    origen = models.CharField(max_length=200)
    destino = models.CharField(max_length=200)
    fecha_hora = models.DateTimeField()
    estado = models.CharField(
        max_length=20,
        db_comment='PENDIENTE | ASIGNADO | EN_CURSO | COMPLETADO | CANCELADO',
    )
    canal_entrada = models.CharField(
        max_length=20,
        db_comment='TELEFONO | APP | PRESENCIAL',
    )
    observaciones = models.CharField(max_length=500, blank=True, null=True)
    fecha_asignacion = models.DateTimeField(blank=True, null=True)
    fecha_inicio = models.DateTimeField(blank=True, null=True)
    fecha_termino = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'solicitudes'
        db_table_comment = 'Solicitudes de servicio gestionadas por la central'

    def __str__(self):
        return self.folio


class Bloqueo(models.Model):
    id_bloqueo = models.FloatField(primary_key=True)
    socio = models.ForeignKey(
        'usuarios.Socio',
        models.DO_NOTHING,
        db_column='id_socio',
        related_name='bloqueos',
    )
    usuario_registra = models.ForeignKey(
        'usuarios.Usuario',
        models.DO_NOTHING,
        db_column='id_usuario_registra',
        blank=True,
        null=True,
        related_name='bloqueos_registrados',
    )
    motivo = models.CharField(max_length=200)
    tipo_bloqueo = models.CharField(
        max_length=30,
        db_comment='CUOTA_VENCIDA | DISCIPLINARIO | MANUAL | OTRO',
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(blank=True, null=True)
    activo = models.BooleanField(db_comment='1=vigente, 0=levantado')

    class Meta:
        managed = False
        db_table = 'bloqueos'
        db_table_comment = 'Bloqueos de socios – impiden ingresar a la fila de servicio'

    def __str__(self):
        return f'Bloqueo {self.id_bloqueo} – {self.socio_id}'


class Cuota(models.Model):
    id_cuota = models.FloatField(primary_key=True)
    socio = models.ForeignKey(
        'usuarios.Socio',
        models.DO_NOTHING,
        db_column='id_socio',
        related_name='cuotas',
    )
    periodo = models.DateField()
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    estado_pago = models.CharField(
        max_length=20,
        db_comment='PENDIENTE | PAGADO | VENCIDO | EXENTO',
    )
    fecha_vencimiento = models.DateField(
        db_comment='Si se supera sin pago, Django crea un BLOQUEO automático',
    )
    fecha_pago = models.DateField(blank=True, null=True)
    observacion = models.CharField(max_length=300, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'cuotas'
        unique_together = (('socio', 'periodo'),)
        db_table_comment = 'Cuotas mensuales – gestionadas por el Tesorero'

    def __str__(self):
        return f'Cuota {self.socio_id} – {self.periodo}'
