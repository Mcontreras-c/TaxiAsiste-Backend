from django.core.management.base import BaseCommand
from django.utils import timezone

from taxiasiste.socios.models import Bloqueo, Cuota


class Command(BaseCommand):
    help = 'Bloquea socios con cuotas vencidas sin bloqueo activo.'

    def handle(self, *args, **kwargs):
        hoy = timezone.now().date()
        cuotas_vencidas = Cuota.objects.filter(
            estado_pago__in=['PENDIENTE', 'VENCIDO'],
            fecha_vencimiento__lt=hoy,
        ).select_related('socio')

        bloqueados = 0
        actualizadas = 0

        for cuota in cuotas_vencidas:
            socio = cuota.socio

            # Marcar cuota como VENCIDO
            if cuota.estado_pago != 'VENCIDO':
                cuota.estado_pago = 'VENCIDO'
                cuota.save(update_fields=['estado_pago'])
                actualizadas += 1

            # Crear bloqueo solo si no tiene uno activo por cuota vencida
            ya_bloqueado = Bloqueo.objects.filter(
                socio=socio,
                tipo_bloqueo='CUOTA_VENCIDA',
                activo=1,
            ).exists()

            if not ya_bloqueado:
                Bloqueo.objects.create(
                    socio=socio,
                    motivo=f'Cuota periodo {cuota.periodo} vencida el {cuota.fecha_vencimiento}',
                    tipo_bloqueo='CUOTA_VENCIDA',
                    fecha_inicio=hoy,
                    activo=1,
                )
                bloqueados += 1
                self.stdout.write(
                    self.style.WARNING(f'  Bloqueado: {socio} — cuota {cuota.periodo}')
                )

        self.stdout.write(self.style.SUCCESS(
            f'\nResumen: {actualizadas} cuotas marcadas VENCIDO, {bloqueados} socios bloqueados.'
        ))
