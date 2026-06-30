from django.db import models


class Rol(models.Model):
    id_rol = models.FloatField(primary_key=True)
    nombre_rol = models.CharField(
        unique=True,
        max_length=30,
        db_comment='Central, Administrador, Tesorero, Conductor',
    )
    descripcion = models.CharField(max_length=200, blank=True, null=True)
    activo = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'roles'
        db_table_comment = 'Roles de acceso al sistema TaxiAsiste'

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
    password_hash = models.CharField(max_length=255, db_comment='Hash gestionado por Django')
    email = models.CharField(unique=True, max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=20, db_comment='ACTIVO | INACTIVO | BLOQUEADO')
    fecha_creacion = models.DateField()
    ultimo_acceso = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'usuarios'
        db_table_comment = 'Usuarios con acceso al sistema'

    def __str__(self):
        return self.username


class Socio(models.Model):
    id_socio = models.FloatField(primary_key=True)
    usuario = models.OneToOneField(
        Usuario,
        models.DO_NOTHING,
        db_column='id_usuario',
        blank=True,
        null=True,
        related_name='socio',
        db_comment='FK opcional – solo si el socio tiene login',
    )
    rut = models.CharField(unique=True, max_length=12, db_comment='Formato: 12345678-9')
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    estado_socio = models.CharField(max_length=20)
    fecha_ingreso = models.DateField()
    fecha_egreso = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'socios'
        db_table_comment = 'Conductores miembros del sindicato'

    def __str__(self):
        return f'{self.nombre} {self.apellido}'


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
    activo = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'pasajeros'
        db_table_comment = 'Pasajeros frecuentes – autocompletar por RUT en la central'

    def __str__(self):
        return f'{self.nombre} {self.apellido}'
