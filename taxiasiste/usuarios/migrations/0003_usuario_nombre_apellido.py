# Generado a mano -- ver 0002_usuario_sesion_actual.py: el autodetector de
# Django no propone cambios para este modelo (managed=False).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0002_usuario_sesion_actual'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='nombre',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=100,
                db_comment='Solo para usuarios sin Socio vinculado (personal del sindicato) -- '
                           'un Conductor muestra el nombre de su Socio, no este campo.',
            ),
        ),
        migrations.AddField(
            model_name='usuario',
            name='apellido',
            field=models.CharField(blank=True, null=True, max_length=100),
        ),
    ]
