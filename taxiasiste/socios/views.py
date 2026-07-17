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
