# Generado a mano: el autodetector de Django no propone cambios para este
# modelo (managed=False) por un problema preexistente no relacionado
# (el campo 'rol' tampoco quedo registrado en 0001_initial).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='sesion_actual',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=64,
                db_comment='ID de la sesion JWT activa. Un login nuevo la reemplaza e invalida la anterior.',
            ),
        ),
    ]
