from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from taxiasiste.socios.models import Bloqueo, Cuota, Socio
from taxiasiste.moviles.models import Movil
from taxiasiste.solicitudes.models import Solicitud

from .models import HistorialEvento
from .serializers import HistorialEventoSerializer


class HistorialEventoViewSet(ReadOnlyModelViewSet):
    queryset = HistorialEvento.objects.select_related('usuario').order_by('-fecha_hora')
    serializer_class = HistorialEventoSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        entidad_tipo = self.request.query_params.get('entidad_tipo')
        entidad_id = self.request.query_params.get('entidad_id')
        if entidad_tipo:
            qs = qs.filter(entidad_tipo=entidad_tipo.upper())
        if entidad_id:
            qs = qs.filter(entidad_id=entidad_id)
        return qs


@api_view(['GET'])
def dashboard(request):
    """Resumen general para el panel principal."""
    hoy = timezone.now().date()

    socios_activos = Socio.objects.filter(estado_socio='ACTIVO').count()
    socios_bloqueados = Socio.objects.filter(estado_socio='BLOQUEADO').count()

    moviles_disponibles = Movil.objects.filter(estado_operativo='DISPONIBLE').count()
    moviles_en_servicio = Movil.objects.filter(estado_operativo='EN_SERVICIO').count()

    solicitudes_hoy = Solicitud.objects.filter(fecha_hora__date=hoy).count()
    solicitudes_pendientes = Solicitud.objects.filter(estado='PENDIENTE').count()
    solicitudes_en_curso = Solicitud.objects.filter(estado__in=['ASIGNADO', 'EN_CURSO']).count()
    solicitudes_completadas_hoy = Solicitud.objects.filter(
        estado='COMPLETADO', fecha_termino__date=hoy
    ).count()

    cuotas_pendientes = Cuota.objects.filter(estado_pago='PENDIENTE').count()
    cuotas_vencidas = Cuota.objects.filter(
        estado_pago__in=['PENDIENTE', 'VENCIDO'],
        fecha_vencimiento__lt=hoy,
    ).count()

    return Response({
        'socios': {
            'activos': socios_activos,
            'bloqueados': socios_bloqueados,
        },
        'moviles': {
            'disponibles': moviles_disponibles,
            'en_servicio': moviles_en_servicio,
        },
        'solicitudes': {
            'hoy': solicitudes_hoy,
            'pendientes': solicitudes_pendientes,
            'en_curso': solicitudes_en_curso,
            'completadas_hoy': solicitudes_completadas_hoy,
        },
        'cuotas': {
            'pendientes': cuotas_pendientes,
            'vencidas': cuotas_vencidas,
        },
        'fecha': hoy,
    })


@api_view(['GET'])
def solicitudes_por_estado(request):
    """Conteo de solicitudes agrupado por estado."""
    from django.db.models import Count
    estados = Solicitud.objects.values('estado').annotate(total=Count('id_solicitud')).order_by('estado')
    return Response(list(estados))


@api_view(['GET'])
def socios_bloqueados(request):
    """Lista de socios con bloqueo activo."""
    bloqueos = Bloqueo.objects.filter(activo=1).select_related('socio').order_by('-fecha_inicio')
    data = [
        {
            'id_bloqueo': b.id_bloqueo,
            'socio': str(b.socio),
            'rut': b.socio.rut,
            'motivo': b.motivo,
            'tipo_bloqueo': b.tipo_bloqueo,
            'fecha_inicio': b.fecha_inicio,
            'fecha_fin': b.fecha_fin,
        }
        for b in bloqueos
    ]
    return Response(data)


@api_view(['GET'])
def cuotas_vencidas(request):
    """Cuotas sin pagar con fecha de vencimiento pasada."""
    hoy = timezone.now().date()
    cuotas = Cuota.objects.filter(
        estado_pago__in=['PENDIENTE', 'VENCIDO'],
        fecha_vencimiento__lt=hoy,
    ).select_related('socio').order_by('fecha_vencimiento')
    data = [
        {
            'id_cuota': c.id_cuota,
            'socio': str(c.socio),
            'rut': c.socio.rut,
            'periodo': c.periodo,
            'monto': c.monto,
            'fecha_vencimiento': c.fecha_vencimiento,
            'estado_pago': c.estado_pago,
        }
        for c in cuotas
    ]
    return Response(data)
