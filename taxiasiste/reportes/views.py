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
def resumen_tesorero(request):
    """
    Resumen financiero por período para el Tesorero.
    ?periodo=YYYY-MM  (default: mes actual)
    Devuelve esperado, cobrado, pendientes y detalle por socio.
    """
    from django.db.models import Sum, Q
    from taxiasiste.moviles.models import Movil

    periodo = request.query_params.get('periodo') or timezone.now().strftime('%Y-%m')
    anio, mes = periodo.split('-')

    cuotas = (
        Cuota.objects
        .filter(periodo__year=anio, periodo__month=mes)
        .select_related('socio')
        .order_by('socio__nombre')
    )

    esperado   = cuotas.aggregate(t=Sum('monto'))['t'] or 0
    cobrado    = cuotas.filter(estado_pago='PAGADO').aggregate(t=Sum('monto'))['t'] or 0
    pendiente  = cuotas.filter(estado_pago__in=['PENDIENTE', 'VENCIDO']).aggregate(t=Sum('monto'))['t'] or 0

    detalle = [
        {
            'id_cuota':       c.id_cuota,
            'id_socio':       c.socio.id_socio,
            'rut':            c.socio.rut,
            'socio':          str(c.socio),
            'monto':          float(c.monto),
            'estado_pago':    c.estado_pago,
            'fecha_vencimiento': c.fecha_vencimiento,
            'fecha_pago':     c.fecha_pago,
        }
        for c in cuotas
    ]

    moviles_activos = Movil.objects.filter(
        estado_operativo__in=['DISPONIBLE', 'EN_SERVICIO']
    ).count()

    return Response({
        'periodo':         periodo,
        'moviles_activos': moviles_activos,
        'esperado':        float(esperado),
        'cobrado':         float(cobrado),
        'pendiente':       float(pendiente),
        'porcentaje':      round((float(cobrado) / float(esperado) * 100) if esperado else 0, 1),
        'detalle':         detalle,
    })


@api_view(['POST'])
def cerrar_periodo(request):
    """
    Marca como VENCIDO todas las cuotas PENDIENTE cuya fecha_vencimiento ya pasó
    y genera bloqueos para esos socios (llama al mismo código que bloquear_morosos).
    """
    from taxiasiste.socios.models import Bloqueo
    from taxiasiste.utils.oracle_seq import nextval

    hoy = timezone.now().date()
    cuotas_morosas = list(
        Cuota.objects.filter(estado_pago='PENDIENTE', fecha_vencimiento__lt=hoy).select_related('socio')
    )
    total_vencidas = len(cuotas_morosas)

    bloqueados = 0
    for cuota in cuotas_morosas:
        cuota.estado_pago = 'VENCIDO'
        cuota.save(update_fields=['estado_pago'])

        ya_bloqueado = Bloqueo.objects.filter(
            socio=cuota.socio, activo=1, tipo_bloqueo='CUOTA_VENCIDA'
        ).exists()
        if not ya_bloqueado:
            bloqueo = Bloqueo()
            bloqueo.id_bloqueo      = nextval('seq_bloqueos')
            bloqueo.socio           = cuota.socio
            bloqueo.motivo          = f'Cuota vencida período {cuota.periodo}'
            bloqueo.tipo_bloqueo    = 'CUOTA_VENCIDA'
            bloqueo.fecha_inicio    = hoy
            bloqueo.activo          = 1
            bloqueo.save()

            socio = cuota.socio
            socio.estado_socio = 'BLOQUEADO'
            socio.save(update_fields=['estado_socio'])
            bloqueados += 1

    return Response({
        'cuotas_vencidas':    total_vencidas,
        'socios_bloqueados':  bloqueados,
        'fecha':              hoy,
    })


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
