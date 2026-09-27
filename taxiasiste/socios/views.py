from datetime import date

from django.db.models import Sum
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from taxiasiste.usuarios.bajas import BajaError, dar_de_baja_socio, reactivar_socio
from taxiasiste.usuarios.permissions import EsAdministrador

from .models import Bloqueo, Cuota, Socio, TesoreriaMovimiento
from .serializers import BloqueoSerializer, CuotaSerializer, SocioSerializer, TesoreriaMovimientoSerializer


class SocioViewSet(ModelViewSet):
    queryset = Socio.objects.select_related('usuario').all()
    serializer_class = SocioSerializer
    # Sin DELETE (405): un socio se da de baja (INACTIVO), nunca se borra.
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ('dar_de_baja', 'reactivar'):
            return [EsAdministrador()]
        return super().get_permissions()

    @action(detail=True, methods=['post'])
    def dar_de_baja(self, request, pk=None):
        """
        Socio INACTIVO con fecha de egreso hoy; su cuenta y su movil quedan
        inactivos, sale de la fila y se borra su ubicacion. El historial se conserva.
        """
        socio = self.get_object()
        try:
            dar_de_baja_socio(socio, request.user)
        except BajaError as e:
            return Response({'detail': e.detail}, status=409)
        socio.refresh_from_db()
        return Response(SocioSerializer(socio).data)

    @action(detail=True, methods=['post'])
    def reactivar(self, request, pk=None):
        """Vuelve a dejar ACTIVO al socio, su cuenta y su movil (no lo pone de nuevo en la fila)."""
        socio = self.get_object()
        try:
            reactivar_socio(socio)
        except BajaError as e:
            return Response({'detail': e.detail}, status=409)
        socio.refresh_from_db()
        return Response(SocioSerializer(socio).data)

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
    def bloquear(self, request, pk=None):
        """
        Bloqueo manual del socio por cualquier motivo administrativo
        (disciplinario, u otro — no necesariamente por no pago).
        Body: { motivo: str, tipo_bloqueo?: 'DISCIPLINARIO'|'MANUAL'|'OTRO' }
        """
        from taxiasiste.utils.oracle_seq import nextval

        socio = self.get_object()
        motivo = (request.data.get('motivo') or '').strip() or 'Bloqueo manual'
        tipo_bloqueo = request.data.get('tipo_bloqueo') or 'DISCIPLINARIO'
        hoy = timezone.now().date()

        ya_bloqueado = Bloqueo.objects.filter(socio=socio, activo=1).exists()
        if not ya_bloqueado:
            bloqueo = Bloqueo()
            bloqueo.id_bloqueo = nextval('seq_bloqueos')
            bloqueo.socio = socio
            bloqueo.usuario_registra = request.user
            bloqueo.motivo = motivo
            bloqueo.tipo_bloqueo = tipo_bloqueo
            bloqueo.fecha_inicio = hoy
            bloqueo.activo = 1
            bloqueo.save()

        socio.estado_socio = 'BLOQUEADO'
        socio.save(update_fields=['estado_socio'])
        return Response({'message': f'{socio} bloqueado.', 'estado_socio': socio.estado_socio})

    @action(detail=True, methods=['post'])
    def desbloquear(self, request, pk=None):
        """
        Reactiva al socio directamente (sin exigir que pague cuotas primero).
        Util para bloqueos manuales o heredados de datos de prueba que no
        tienen ninguna cuota real asociada — pagar_atrasos no sirve ahi porque
        no hay nada que pagar.
        """
        socio = self.get_object()
        Bloqueo.objects.filter(socio=socio, activo=1).update(activo=0, fecha_fin=timezone.now().date())
        socio.estado_socio = 'ACTIVO'
        socio.save(update_fields=['estado_socio'])
        return Response({'message': f'{socio} desbloqueado.', 'estado_socio': socio.estado_socio})


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

    @action(detail=False, methods=['get'])
    def resumen_mensual(self, request):
        """
        Resumen de caja del mes, igual al calculo manual que se hacia en papel:
        Caja mes anterior (todo lo acumulado antes del mes) + Ganancias del mes
        (ingresos) - Gastos del mes (egresos) = Total caja al cierre del mes.
        ?mes=YYYY-MM  (default: mes actual)
        """
        import calendar

        mes_str = request.query_params.get('mes') or timezone.now().strftime('%Y-%m')
        anio, mes = (int(x) for x in mes_str.split('-'))
        primer_dia = date(anio, mes, 1)
        ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])

        qs = TesoreriaMovimiento.objects.all()

        anteriores = qs.filter(fecha__lt=primer_dia)
        caja_anterior = (
            (anteriores.filter(tipo='INGRESO').aggregate(t=Sum('monto'))['t'] or 0)
            - (anteriores.filter(tipo='EGRESO').aggregate(t=Sum('monto'))['t'] or 0)
        )

        del_mes = qs.filter(fecha__gte=primer_dia, fecha__lte=ultimo_dia)
        ingresos_mes = del_mes.filter(tipo='INGRESO').aggregate(t=Sum('monto'))['t'] or 0
        egresos_mes = del_mes.filter(tipo='EGRESO').aggregate(t=Sum('monto'))['t'] or 0

        return Response({
            'mes':             mes_str,
            'caja_anterior':   float(caja_anterior),
            'ingresos_mes':    float(ingresos_mes),
            'egresos_mes':     float(egresos_mes),
            'total_caja':      float(caja_anterior) + float(ingresos_mes) - float(egresos_mes),
        })

    @action(detail=False, methods=['post'])
    def pagar_movil(self, request):
        """
        Registra el pago de cuota semanal de un móvil.
        Si la cuota no existe, la crea. Si ya existe, la marca como PAGADO.
        Body: { id_socio, monto, periodo (YYYY-MM-DD — lunes de la semana) }
        """
        from taxiasiste.utils.oracle_seq import nextval

        id_socio = request.data.get('id_socio')
        monto    = request.data.get('monto')
        periodo_str = request.data.get('periodo')  # YYYY-MM-DD (lunes)

        if not id_socio or not monto or not periodo_str:
            return Response({'error': 'id_socio, monto y periodo son requeridos.'}, status=400)

        try:
            socio = Socio.objects.get(pk=id_socio)
        except Socio.DoesNotExist:
            return Response({'error': 'Socio no encontrado.'}, status=404)

        periodo_date = date.fromisoformat(periodo_str)
        # Vencimiento: fin de esa semana (domingo)
        vencimiento = periodo_date + timezone.timedelta(days=6)

        hoy = timezone.now().date()
        cuota = Cuota.objects.filter(socio=socio, periodo=periodo_date).first()

        if not cuota:
            cuota = Cuota()
            cuota.id_cuota         = nextval('seq_cuotas')
            cuota.socio            = socio
            cuota.periodo          = periodo_date
            cuota.monto            = monto
            cuota.fecha_vencimiento = vencimiento
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
