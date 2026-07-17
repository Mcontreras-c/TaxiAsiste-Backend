from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Bloqueo, Cuota, Socio, TesoreriaMovimiento
from .serializers import BloqueoSerializer, CuotaSerializer, SocioSerializer, TesoreriaMovimientoSerializer


class SocioViewSet(ModelViewSet):
    queryset = Socio.objects.select_related('usuario').all()
    serializer_class = SocioSerializer

    @action(detail=True, methods=['get'])
    def cuotas(self, request, pk=None):
        """Historial completo de cuotas del socio."""
        socio = self.get_object()
        qs = Cuota.objects.filter(socio=socio).order_by('-periodo')
        return Response(CuotaSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'])
    def bloqueos(self, request, pk=None):
        """Historial completo de bloqueos del socio."""
        socio = self.get_object()
        qs = Bloqueo.objects.filter(socio=socio).order_by('-fecha_inicio')
        return Response(BloqueoSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'])
    def bloqueos_activos(self, request, pk=None):
        """Solo bloqueos vigentes (activo=1)."""
        socio = self.get_object()
        qs = Bloqueo.objects.filter(socio=socio, activo=1)
        return Response(BloqueoSerializer(qs, many=True).data)


class CuotaViewSet(ModelViewSet):
    queryset = Cuota.objects.select_related('socio').order_by('-periodo')
    serializer_class = CuotaSerializer


class BloqueoViewSet(ModelViewSet):
    queryset = Bloqueo.objects.select_related('socio', 'usuario_registra').order_by('-fecha_inicio')
    serializer_class = BloqueoSerializer


class TesoreriaMovimientoViewSet(ModelViewSet):
    queryset = TesoreriaMovimiento.objects.select_related(
        'usuario_registra', 'cuota'
    ).order_by('-fecha')
    serializer_class = TesoreriaMovimientoSerializer

    @action(detail=False, methods=['get'])
    def balance(self, request):
        """Resumen financiero: total ingresos, egresos y balance."""
        from django.db.models import Sum
        qs = TesoreriaMovimiento.objects.all()
        ingresos = qs.filter(tipo='INGRESO').aggregate(total=Sum('monto'))['total'] or 0
        egresos  = qs.filter(tipo='EGRESO').aggregate(total=Sum('monto'))['total'] or 0
        return Response({
            'ingresos': float(ingresos),
            'egresos':  float(egresos),
            'balance':  float(ingresos - egresos),
            'fecha':    timezone.now().date().isoformat(),
        })

    @action(detail=False, methods=['post'])
    def pagar_movil(self, request):
        """
        Registra el pago de cuota de un móvil para un período.
        Si la cuota no existe, la crea. Si ya existe, la marca como PAGADO.
        Body: { id_socio, monto, periodo (YYYY-MM) }
        """
        from taxiasiste.utils.oracle_seq import nextval
        import datetime

        id_socio = request.data.get('id_socio')
        monto    = request.data.get('monto')
        periodo_str = request.data.get('periodo')  # YYYY-MM

        if not id_socio or not monto or not periodo_str:
            return Response({'error': 'id_socio, monto y periodo son requeridos.'}, status=400)

        try:
            socio = Socio.objects.get(pk=id_socio)
        except Socio.DoesNotExist:
            return Response({'error': 'Socio no encontrado.'}, status=404)

        anio, mes = periodo_str.split('-')
        # Fecha de vencimiento: último día del mes
        ultimo_dia = (datetime.date(int(anio), int(mes) % 12 + 1, 1) - datetime.timedelta(days=1)
                      if int(mes) < 12
                      else datetime.date(int(anio), 12, 31))

        # Buscar cuota existente para el período
        hoy = timezone.now().date()
        periodo_date = datetime.date(int(anio), int(mes), 1)
        cuota = Cuota.objects.filter(socio=socio, periodo__year=anio, periodo__month=mes).first()

        if not cuota:
            cuota = Cuota()
            cuota.id_cuota         = nextval('seq_cuotas')
            cuota.socio            = socio
            cuota.periodo          = periodo_date
            cuota.monto            = monto
            cuota.fecha_vencimiento = ultimo_dia
            cuota.estado_pago      = 'PENDIENTE'
            cuota.save()

        if cuota.estado_pago == 'PAGADO':
            return Response({'error': 'Esta cuota ya está pagada.'}, status=400)

        cuota.estado_pago = 'PAGADO'
        cuota.fecha_pago  = hoy
        cuota.save()

        mov = TesoreriaMovimiento()
        mov.id_movimiento   = nextval('seq_tesoreria_mov')
        mov.usuario_registra = request.user
        mov.cuota            = cuota
        mov.tipo             = 'INGRESO'
        mov.categoria        = 'CUOTA'
        mov.descripcion      = f'Pago cuota {periodo_str} — {socio}'
        mov.monto            = cuota.monto
        mov.fecha            = hoy
        mov.save()

        return Response({
            'message':    'Pago registrado correctamente.',
            'id_cuota':   cuota.id_cuota,
            'estado_pago':'PAGADO',
        })

    @action(detail=False, methods=['post'])
    def registrar_pago_cuota(self, request):
        """Marca una cuota como PAGADA y crea el movimiento de ingreso."""
        id_cuota = request.data.get('id_cuota')
        observacion = request.data.get('observacion', '')
        try:
            cuota = Cuota.objects.get(pk=id_cuota)
        except Cuota.DoesNotExist:
            return Response({'error': 'Cuota no encontrada.'}, status=404)

        if cuota.estado_pago == 'PAGADO':
            return Response({'error': 'La cuota ya está pagada.'}, status=400)

        cuota.estado_pago = 'PAGADO'
        cuota.fecha_pago = timezone.now().date()
        if observacion:
            cuota.observacion = observacion
        cuota.save()

        mov = TesoreriaMovimiento(
            usuario_registra=request.user,
            cuota=cuota,
            tipo='INGRESO',
            categoria='CUOTA',
            descripcion=f'Pago cuota {cuota.periodo} — {cuota.socio}',
            monto=cuota.monto,
            fecha=timezone.now().date(),
        )
        mov.save()

        return Response({
            'message': 'Cuota pagada registrada correctamente.',
            'movimiento': TesoreriaMovimientoSerializer(mov).data,
        })
