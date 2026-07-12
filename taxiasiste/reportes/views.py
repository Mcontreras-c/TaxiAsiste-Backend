from rest_framework.viewsets import ReadOnlyModelViewSet

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
