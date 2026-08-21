from django.db import models

from taxiasiste.utils.oracle_seq import nextval


class Rol(models.Model):
    id_rol = models.FloatField(primary_key=True)
    nombre_rol = models.CharField(
        unique=True,
        max_length=30,
        db_comment='Administrador, Central, Tesorero, Conductor',
    )
    descripcion = models.CharField(max_length=200, blank=True, null=True)
    activo = models.SmallIntegerField(
        default=1,
        db_comment='1=activo, 0=inactivo',
    )

    class Meta:
        managed = False
        db_table = 'ROLES'
        db_table_comment = 'Roles de acceso al sistema TaxiAsiste'

    def save(self, *args, **kwargs):
        if not self.id_rol:
            self.id_rol = nextval('seq_roles')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre_rol


class Usuario(models.Model):
    id_usuario = models.FloatField(primary_key=True)
    rol = models.ForeignKey(
        Rol,
        models.DO_NOTHING,
        db_column='id_rol',
        related_name='usuarios',
    )
    username = models.CharField(unique=True, max_length=50)
    password_hash = models.CharField(
        max_length=255,
        db_comment='Hash gestionado por Django',
    )
    email = models.CharField(unique=True, max_length=100, blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        default='ACTIVO',
        db_comment='ACTIVO | INACTIVO | BLOQUEADO',
    )
    fecha_creacion = models.DateField()
    ultimo_acceso = models.DateTimeField(blank=True, null=True)
    sesion_actual = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_comment='ID de la sesion JWT activa. Un login nuevo la reemplaza e invalida la anterior.',
    )

    class Meta:
        managed = False
        db_table = 'USUARIOS'
        db_table_comment = 'Usuarios con acceso al sistema'

    def save(self, *args, **kwargs):
        if not self.id_usuario:
            self.id_usuario = nextval('seq_usuarios')
        super().save(*args, **kwargs)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def __str__(self):
        return f'{self.username} ({self.estado})'
