# Generado a mano -- ver 0002_usuario_sesion_actual.py: el autodetector de
# Django no propone cambios para este modelo (managed=False).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0003_usuario_nombre_apellido'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='telefono',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=20,
                db_comment='Solo para usuarios sin Socio vinculado -- un Conductor usa SOCIOS.telefono.',
            ),
        ),
    ]
