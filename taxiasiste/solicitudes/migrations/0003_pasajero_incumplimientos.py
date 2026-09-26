# Generado a mano: el autodetector de Django no propone cambios para modelos
# managed=False ya existentes (ver usuarios/migrations/0002_usuario_sesion_actual.py).
# La columna real la crea scripts/migrar_reservas_postgres.sql.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('solicitudes', '0002_reserva_reservaevento'),
    ]

    operations = [
        migrations.AddField(
            model_name='pasajero',
            name='incumplimientos',
            field=models.SmallIntegerField(
                default=0,
                db_comment='Veces que no se presento a una reserva. Al llegar a PASAJERO_MAX_INCUMPLIMIENTOS se bloquea.',
            ),
        ),
        migrations.AddField(
            model_name='pasajero',
            name='bloqueado_domicilio',
            field=models.SmallIntegerField(
                default=0,
                db_comment='1 = no puede pedir moviles a domicilio (solo un administrador lo levanta)',
            ),
        ),
    ]
