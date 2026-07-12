from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Bloqueo, Cuota, Socio
from .serializers import BloqueoSerializer, CuotaSerializer, SocioSerializer


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
