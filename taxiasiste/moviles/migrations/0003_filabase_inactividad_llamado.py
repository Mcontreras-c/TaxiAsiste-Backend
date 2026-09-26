# Generado a mano -- ver usuarios/migrations/0002_usuario_sesion_actual.py: el
# autodetector de Django no propone cambios para modelos managed=False. Las
# columnas reales las crea scripts/migrar_fila_inactividad_llamado_postgres.sql.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('moviles', '0002_ubicacionactual'),
    ]

    operations = [
        migrations.AddField(
            model_name='filabase',
            name='motivo_salida',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=30,
                db_comment="Por que la saco el sistema: 'inactividad' | 'no_respondio'. NULL si salio por accion de una persona.",
            ),
        ),
        migrations.AddField(
            model_name='filabase',
            name='confirmado_en',
            field=models.DateTimeField(
                blank=True,
                null=True,
                db_comment="Cuando el conductor pulso 'Voy' despues de ser llamado.",
            ),
        ),
        migrations.AddField(
            model_name='filabase',
            name='no_respuestas',
            field=models.IntegerField(
                default=0,
                db_comment='Llamados seguidos sin confirmar; con 2 se retira. Vuelve a 0 al confirmar.',
            ),
        ),
    ]
