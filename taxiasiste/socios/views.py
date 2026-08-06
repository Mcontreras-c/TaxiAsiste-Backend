from django.db.models import Sum
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

    @action(detail=True, methods=['post'])
    def bloquear_por_no_pago(self, request, pk=None):
        """
        Bloqueo manual inmediato por no pago (el Tesorero no necesita esperar
        al cierre de periodo de los viernes). Si el socio ya tenia una cuota
        PENDIENTE para el periodo indicado, la marca VENCIDO de una vez para
        que sume al monto adeudado acumulado, igual que hace el cierre
        automatico.
        Body opcional: { periodo: 'YYYY-MM' } (default: mes actual)
        """
        from taxiasiste.utils.oracle_seq import nextval

        socio = self.get_object()
        hoy = timezone.now().date()
        periodo_str = request.data.get('periodo') or hoy.strftime('%Y-%m')
        anio, mes = periodo_str.split('-')

        cuota_periodo = Cuota.objects.filter(socio=socio, periodo__year=anio, periodo__month=mes).first()
        if cuota_periodo and cuota_periodo.estado_pago == 'PENDIENTE':
            cuota_periodo.estado_pago = 'VENCIDO'
            cuota_periodo.save(update_fields=['estado_pago'])

        ya_bloqueado = Bloqueo.objects.filter(socio=socio, activo=1, tipo_bloqueo='CUOTA_VENCIDA').exists()
        if not ya_bloqueado:
            bloqueo = Bloqueo()
            bloqueo.id_bloqueo = nextval('seq_bloqueos')
            bloqueo.socio = socio
            bloqueo.usuario_registra = request.user
            bloqueo.motivo = f'Bloqueo manual por no pago — período {periodo_str}'
            bloqueo.tipo_bloqueo = 'CUOTA_VENCIDA'
            bloqueo.fecha_inicio = hoy
            bloqueo.activo = 1
            bloqueo.save()

        socio.estado_socio = 'BLOQUEADO'
        socio.save(update_fields=['estado_socio'])

        monto_adeudado = Cuota.objects.filter(
            socio=socio, estado_pago__in=['PENDIENTE', 'VENCIDO'],
        ).aggregate(total=Sum('monto'))['total'] or 0

        return Response({
            'message': f'{socio} bloqueado por no pago.',
            'estado_socio': socio.estado_socio,
            'monto_adeudado': float(monto_adeudado),
        })


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
    def pagar_atrasos(self, request):
        """
        Paga todas las cuotas PENDIENTE/VENCIDO de un socio moroso,
        crea un movimiento de ingreso por cada una, desactiva sus bloqueos
        y reactiva al socio.
        Body: { id_socio }
        """
        from taxiasiste.utils.oracle_seq import nextval

        id_socio = request.data.get('id_socio')
        if not id_socio:
            return Response({'error': 'id_socio es requerido.'}, status=400)

        try:
            socio = Socio.objects.get(pk=id_socio)
        except Socio.DoesNotExist:
            return Response({'error': 'Socio no encontrado.'}, status=404)

        hoy = timezone.now().date()
        cuotas_atrasadas = list(
            Cuota.objects.filter(
                socio=socio,
                estado_pago__in=['PENDIENTE', 'VENCIDO'],
                fecha_vencimiento__lt=hoy,
            ).order_by('periodo')
        )

        if not cuotas_atrasadas:
            return Response({'error': 'Este socio no tiene cuotas atrasadas.'}, status=400)

        total_pagado = 0
        movimientos_ids = []
        for cuota in cuotas_atrasadas:
            cuota.estado_pago = 'PAGADO'
            cuota.fecha_pago  = hoy
            cuota.save()

            mov = TesoreriaMovimiento()
            mov.id_movimiento    = nextval('seq_tesoreria_mov')
            mov.usuario_registra = request.user
            mov.cuota            = cuota
            mov.tipo             = 'INGRESO'
            mov.categoria        = 'CUOTA'
            mov.descripcion      = f'Pago atraso cuota {cuota.periodo.strftime("%Y-%m")} — {socio}'
            mov.monto            = cuota.monto
            mov.fecha            = hoy
            mov.save()
            total_pagado += float(cuota.monto)
            movimientos_ids.append(mov.id_movimiento)

        # Desactivar todos los bloqueos CUOTA_VENCIDA activos del socio
        Bloqueo.objects.filter(socio=socio, activo=1, tipo_bloqueo='CUOTA_VENCIDA').update(
            activo=0, fecha_fin=hoy
        )

        # Reactivar socio solo si no tiene otros bloqueos activos
        tiene_otros_bloqueos = Bloqueo.objects.filter(socio=socio, activo=1).exists()
        if not tiene_otros_bloqueos:
            socio.estado_socio = 'ACTIVO'
            socio.save(update_fields=['estado_socio'])

        return Response({
            'message':       f'{len(cuotas_atrasadas)} cuota(s) pagada(s). Socio desbloqueado.',
            'cuotas_pagadas': len(cuotas_atrasadas),
            'total_pagado':  total_pagado,
            'estado_socio':  socio.estado_socio,
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
