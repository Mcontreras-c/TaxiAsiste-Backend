from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from taxiasiste.socios.models import Bloqueo, Cuota, Socio
from taxiasiste.moviles.models import Movil
from taxiasiste.solicitudes.models import Solicitud

from taxiasiste.usuarios.permissions import EsAdministrador

from .models import HistorialEvento
from .serializers import HistorialEventoSerializer


class HistorialEventoViewSet(ReadOnlyModelViewSet):
    queryset = HistorialEvento.objects.select_related('usuario').order_by('-fecha_hora')
    serializer_class = HistorialEventoSerializer
    permission_classes = [EsAdministrador]  # quien hizo que: solo Administrador

    def get_queryset(self):
        qs = super().get_queryset()
        entidad_tipo = self.request.query_params.get('entidad_tipo')
        entidad_id = self.request.query_params.get('entidad_id')
        if entidad_tipo:
            qs = qs.filter(entidad_tipo=entidad_tipo.upper())
        if entidad_id:
            qs = qs.filter(entidad_id=entidad_id)
        return qs

    def list(self, request, *args, **kwargs):
        # Sin paginacion global: se acota a los mas recientes (?limit=, maximo 500).
        try:
            limite = min(int(request.query_params.get('limit', 200)), 500)
        except ValueError:
            limite = 200
        return Response(self.get_serializer(self.filter_queryset(self.get_queryset())[:limite], many=True).data)


@api_view(['GET'])
def dashboard(request):
    """Resumen general para el panel principal."""
    hoy = timezone.now().date()

    socios_activos = Socio.objects.filter(estado_socio='ACTIVO').count()
    socios_bloqueados = Socio.objects.filter(estado_socio='BLOQUEADO').count()

    moviles_disponibles = Movil.objects.filter(estado_operativo='DISPONIBLE').count()
    # EN_SERVICIO (voy a buscar al pasajero) y EN_VIAJE (pasajero a bordo) son
    # ambos "movil ocupado con un servicio" para el resumen del panel.
    moviles_en_servicio = Movil.objects.filter(estado_operativo__in=['EN_SERVICIO', 'EN_VIAJE']).count()

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
    Resumen financiero por semana para el Tesorero.
    ?periodo=YYYY-MM-DD  (lunes de la semana; default: semana actual)
    Devuelve todos los móviles activos con su estado de pago para esa semana.
    """
    from datetime import date, timedelta

    from django.db.models import Sum
    from taxiasiste.moviles.models import Movil

    hoy = timezone.now().date()
    periodo_str = request.query_params.get('periodo') or (hoy - timedelta(days=hoy.weekday())).isoformat()
    periodo_date = date.fromisoformat(periodo_str)

    # Todos los móviles con su socio (sin filtrar por estado)
    moviles = (
        Movil.objects
        .exclude(estado_operativo='INACTIVO')
        .select_related('socio')
        .order_by('socio__nombre')
    )

    # Cuotas de la semana indexadas por socio
    cuotas_periodo = {
        c.socio_id: c
        for c in Cuota.objects.filter(periodo=periodo_date)
    }

    # Cuotas vencidas (PENDIENTE/VENCIDO con fecha pasada) por socio
    hoy = timezone.now().date()
    from django.db.models import Count, Sum
    vencidas_por_socio = {
        row['socio_id']: row['total']
        for row in Cuota.objects
            .filter(estado_pago__in=['PENDIENTE', 'VENCIDO'], fecha_vencimiento__lt=hoy)
            .values('socio_id')
            .annotate(total=Count('id_cuota'))
    }

    # Monto total adeudado (todas las cuotas sin pagar, vencidas o no) por socio —
    # es acumulativo por diseño: cada periodo sin pagar es una fila CUOTA aparte.
    adeudado_por_socio = {
        row['socio_id']: float(row['total'] or 0)
        for row in Cuota.objects
            .filter(estado_pago__in=['PENDIENTE', 'VENCIDO'])
            .values('socio_id')
            .annotate(total=Sum('monto'))
    }

    detalle = []
    for m in moviles:
        cuota = cuotas_periodo.get(m.socio_id)
        detalle.append({
            'id_movil':        m.id_movil,
            'patente':         m.patente,
            'estado_movil':    m.estado_operativo,
            'id_socio':        m.socio.id_socio,
            'rut':             m.socio.rut,
            'socio':           str(m.socio),
            'estado_socio':    m.socio.estado_socio,
            'id_cuota':        cuota.id_cuota if cuota else None,
            'monto':           float(cuota.monto) if cuota else 0,
            'estado_pago':     cuota.estado_pago if cuota else 'SIN_CUOTA',
            'fecha_pago':      cuota.fecha_pago if cuota else None,
            'cuotas_vencidas': vencidas_por_socio.get(m.socio_id, 0),
            'monto_adeudado': adeudado_por_socio.get(m.socio_id, 0),
        })

    cobrado_total  = sum(d['monto'] for d in detalle if d['estado_pago'] == 'PAGADO')
    pagados        = sum(1 for d in detalle if d['estado_pago'] == 'PAGADO')
    pendientes     = len(detalle) - pagados

    return Response({
        'periodo':         periodo_str,
        'semana_fin':      (periodo_date + timedelta(days=6)).isoformat(),
        'total_moviles':   len(detalle),
        'pagados':         pagados,
        'pendientes':      pendientes,
        'cobrado':         cobrado_total,
        'porcentaje':      round((pagados / len(detalle) * 100) if detalle else 0, 1),
        'detalle':         detalle,
    })


@api_view(['POST'])
def cerrar_semana(request):
    """
    Cierra la semana de cobranza: las cuotas ya marcadas PAGADO quedan tal
    cual (ese dinero ya se registró en tesorería al momento del pago); todos
    los móviles/socios sin cuota PAGADO para esa semana quedan VENCIDO y su
    socio se bloquea (bloqueo acumulativo — cada semana sin pago suma un
    bloqueo/cuota nueva, igual que hace bloquear_por_no_pago).
    Body: { periodo: 'YYYY-MM-DD' (lunes de la semana), tarifa: number }
    """
    from datetime import date, timedelta

    from taxiasiste.socios.models import Bloqueo
    from taxiasiste.moviles.models import Movil
    from taxiasiste.utils.oracle_seq import nextval

    periodo_str = request.data.get('periodo')
    tarifa = request.data.get('tarifa')
    if not periodo_str or not tarifa:
        return Response({'error': 'periodo y tarifa son requeridos.'}, status=400)

    periodo_date = date.fromisoformat(periodo_str)
    vencimiento = periodo_date + timedelta(days=6)
    hoy = timezone.now().date()

    moviles = Movil.objects.exclude(estado_operativo='INACTIVO').select_related('socio')
    cuotas_semana = {c.socio_id: c for c in Cuota.objects.filter(periodo=periodo_date)}

    recaudado = 0.0
    socios_bloqueados = 0
    cuotas_vencidas_count = 0
    procesados = set()

    for m in moviles:
        socio = m.socio
        if socio.id_socio in procesados:
            continue
        procesados.add(socio.id_socio)

        cuota = cuotas_semana.get(socio.id_socio)

        if cuota and cuota.estado_pago == 'PAGADO':
            recaudado += float(cuota.monto)
            continue

        if not cuota:
            cuota = Cuota()
            cuota.id_cuota = nextval('seq_cuotas')
            cuota.socio = socio
            cuota.periodo = periodo_date
            cuota.monto = tarifa
            cuota.fecha_vencimiento = vencimiento
            cuota.estado_pago = 'VENCIDO'
            cuota.save()
        elif cuota.estado_pago != 'VENCIDO':
            cuota.estado_pago = 'VENCIDO'
            cuota.save(update_fields=['estado_pago'])
        cuotas_vencidas_count += 1

        ya_bloqueado = Bloqueo.objects.filter(socio=socio, activo=1, tipo_bloqueo='CUOTA_VENCIDA').exists()
        if not ya_bloqueado:
            bloqueo = Bloqueo()
            bloqueo.id_bloqueo = nextval('seq_bloqueos')
            bloqueo.socio = socio
            bloqueo.motivo = f'Cierre de semana sin pago — {periodo_str}'
            bloqueo.tipo_bloqueo = 'CUOTA_VENCIDA'
            bloqueo.fecha_inicio = hoy
            bloqueo.activo = 1
            bloqueo.save()
            socios_bloqueados += 1

        if socio.estado_socio != 'BLOQUEADO':
            socio.estado_socio = 'BLOQUEADO'
            socio.save(update_fields=['estado_socio'])

    return Response({
        'periodo':            periodo_str,
        'recaudado':          recaudado,
        'cuotas_vencidas':    cuotas_vencidas_count,
        'socios_bloqueados':  socios_bloqueados,
        'fecha':              hoy.isoformat(),
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
