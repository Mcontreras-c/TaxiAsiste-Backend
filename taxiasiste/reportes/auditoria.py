"""
Registro de quien hizo que (HISTORIAL_EVENTOS) para las acciones sensibles de
administracion: altas, ediciones, bajas, bloqueos, claves y confirmaciones fallidas.

Nunca guarda contrasenas ni claves. Un fallo al registrar no debe impedir la
accion en si: se deja en el log del servidor y la operacion sigue.
"""
import logging

from .models import HistorialEvento

logger = logging.getLogger(__name__)
MAX_DETALLE = 500


def ip_de(request):
    """IP del cliente (nginx la pasa en X-Forwarded-For)."""
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (reenviada.split(',')[0].strip() or request.META.get('REMOTE_ADDR') or None)


def registrar(request, entidad_tipo, entidad_id, evento, anterior=None, nuevo=None, detalle=None):
    try:
        usuario = request.user if getattr(request.user, 'is_authenticated', False) else None
        HistorialEvento.objects.create(
            usuario=usuario, entidad_tipo=entidad_tipo, entidad_id=int(entidad_id), evento=evento,
            estado_anterior=str(anterior)[:50] if anterior is not None else None,
            estado_nuevo=str(nuevo)[:50] if nuevo is not None else None,
            detalle=detalle[:MAX_DETALLE] if detalle else None, ip_origen=ip_de(request),
        )
    except Exception:  # noqa: BLE001 -- la auditoria nunca debe tumbar la accion
        logger.exception('No se pudo registrar el evento %s %s#%s', evento, entidad_tipo, entidad_id)


class AuditaEdicion:
    """
    Mixin para ModelViewSet: registra, en cada PATCH/PUT, que campos cambiaron y de
    que valor a que valor. Define `auditoria_tipo` y `auditoria_campos`.
    """

    auditoria_tipo = None
    auditoria_campos = ()

    def perform_update(self, serializer):
        antes = {c: getattr(serializer.instance, c, None) for c in self.auditoria_campos}
        instancia = serializer.save()
        cambios = {
            c: (antes[c], getattr(instancia, c, None))
            for c in self.auditoria_campos if antes[c] != getattr(instancia, c, None)
        }
        if not cambios:
            return
        evento = 'EDITADO'
        if list(cambios) == ['estado_operativo']:
            evento = {'BLOQUEADO': 'BLOQUEADO'}.get(cambios['estado_operativo'][1]) or (
                'DESBLOQUEADO' if cambios['estado_operativo'][0] == 'BLOQUEADO' else evento)
        detalle = '; '.join(f'{c}: {a if a not in (None, "") else "—"} → {b if b not in (None, "") else "—"}'
                            for c, (a, b) in cambios.items())
        registrar(self.request, self.auditoria_tipo, instancia.pk, evento, detalle=detalle)
