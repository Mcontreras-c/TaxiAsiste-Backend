from django.conf import settings
from django.core.management.base import BaseCommand

from taxiasiste.moviles import fila_logic


class Command(BaseCommand):
    help = (
        'Reglas de la fila virtual con el paso del tiempo: retira a los móviles EN_ESPERA sin '
        'reportar ubicación por más de FILA_INACTIVIDAD_MIN minutos, y aplica el plazo de '
        'FILA_LLAMADO_SEGUNDOS a los llamados que no pulsaron "Voy" (pasan al final de la fila; '
        'a la segunda vez seguida se retiran). Pensado para correr cada minuto '
        '(timer del sistema); es seguro ejecutarlo más seguido o en paralelo.'
    )

    def handle(self, *args, **options):
        inactivos = fila_logic.retirar_inactivos()
        llamados = fila_logic.procesar_llamados_vencidos()

        self.stdout.write(
            f'Inactividad (>{settings.FILA_INACTIVIDAD_MIN} min): {inactivos} retirado(s). '
            f'Llamados sin "Voy" (>{settings.FILA_LLAMADO_SEGUNDOS} s): '
            f'{llamados["al_final"]} al final de la fila, {llamados["retirados"]} retirado(s).'
        )
