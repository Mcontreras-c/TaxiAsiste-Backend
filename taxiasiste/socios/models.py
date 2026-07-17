from django.db import models

from taxiasiste.utils.oracle_seq import nextval


class Socio(models.Model):
    id_socio = models.FloatField(primary_key=True)
    usuario = models.OneToOneField(
        'usuarios.Usuario',
        models.DO_NOTHING,
        db_column='id_usuario',
        blank=True,
        null=True,
        related_name='socio',
        db_comment='FK opcional — solo si el socio tiene login',
    )
    rut = models.CharField(unique=True, max_length=12, db_comment='Formato: 12345678-9')
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    estado_socio = models.CharField(
        max_length=20,
        default='ACTIVO',
        db_comment='ACTIVO | INACTIVO | BLOQUEADO',
    )
    fecha_ingreso = models.DateField()
    fecha_egreso = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'SOCIOS'
        db_table_comment = 'Conductores miembros del sindicato'

    def save(self, *args, **kwargs):
        if not self.id_socio:
            self.id_socio = nextval('seq_socios')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.nombre} {self.apellido} ({self.rut})'


class Cuota(models.Model):
    id_cuota = models.FloatField(primary_key=True)
    socio = models.ForeignKey(
        Socio,
        models.DO_NOTHING,
        db_column='id_socio',
        related_name='cuotas',
    )
    periodo = models.DateField()
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    estado_pago = models.CharField(
        max_length=20,
        default='PENDIENTE',
        db_comment='PENDIENTE | PAGADO | VENCIDO | EXENTO',
    )
    fecha_vencimiento = models.DateField(
        db_comment='Si se supera sin pago, Django crea un BLOQUEO automático',
    )
    fecha_pago = models.DateField(blank=True, null=True)
    observacion = models.CharField(max_length=300, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'CUOTAS'
        unique_together = (('socio', 'periodo'),)
        db_table_comment = 'Cuotas mensuales — gestionadas por el Tesorero'

    def save(self, *args, **kwargs):
        if not self.id_cuota:
            self.id_cuota = nextval('seq_cuotas')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.socio} | {self.periodo} | {self.estado_pago}'


class Bloqueo(models.Model):
    id_bloqueo = models.FloatField(primary_key=True)
    socio = models.ForeignKey(
        Socio,
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
        default='CUOTA_VENCIDA',
        db_comment='CUOTA_VENCIDA | DISCIPLINARIO | MANUAL | OTRO',
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(blank=True, null=True)
    activo = models.SmallIntegerField(
        default=1,
        db_comment='1=vigente, 0=levantado',
    )

    class Meta:
        managed = False
        db_table = 'BLOQUEOS'
        db_table_comment = 'Bloqueos de socios — impiden ingresar a la fila de servicio'

    def save(self, *args, **kwargs):
        if not self.id_bloqueo:
            self.id_bloqueo = nextval('seq_bloqueos')
        super().save(*args, **kwargs)

    def __str__(self):
        estado = 'vigente' if self.activo else 'levantado'
        return f'Bloqueo {self.tipo_bloqueo} — {self.socio} ({estado})'


class TesoreriaMovimiento(models.Model):
    TIPO_CHOICES = [('INGRESO', 'Ingreso'), ('EGRESO', 'Egreso')]
    CATEGORIA_CHOICES = [
        ('CUOTA', 'Cuota'),
        ('MULTA', 'Multa'),
        ('GASTO_OPERACIONAL', 'Gasto Operacional'),
        ('OTRO', 'Otro'),
    ]

    id_movimiento = models.FloatField(primary_key=True)
    usuario_registra = models.ForeignKey(
        'usuarios.Usuario',
        models.DO_NOTHING,
        db_column='id_usuario_registra',
        blank=True,
        null=True,
        related_name='movimientos_tesoreria',
    )
    cuota = models.ForeignKey(
        Cuota,
        models.DO_NOTHING,
        db_column='id_cuota',
        blank=True,
        null=True,
        related_name='movimientos',
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    categoria = models.CharField(max_length=30, choices=CATEGORIA_CHOICES)
    descripcion = models.CharField(max_length=300)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateField()

    class Meta:
        managed = False
        db_table = 'TESORERIA_MOVIMIENTOS'
        db_table_comment = 'Ingresos y egresos del sindicato — gestionados por el Tesorero'

    def save(self, *args, **kwargs):
        if not self.id_movimiento:
            self.id_movimiento = nextval('seq_tesoreria_mov')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.tipo} | {self.categoria} | ${self.monto} | {self.fecha}'
