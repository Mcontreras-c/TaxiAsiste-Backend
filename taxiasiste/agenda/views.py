from rest_framework.viewsets import ModelViewSet

from .models import EventoAgenda
from .serializers import EventoAgendaSerializer


class EventoAgendaViewSet(ModelViewSet):
    """
    CRUD de reuniones/fechas importantes. Cualquier usuario autenticado con
    acceso al modulo de agenda puede crear/editar -- la restriccion de que
    solo Secretario/Administrador vean la pantalla se maneja en el frontend
    (mismo patron que el resto de los ViewSets de este proyecto).
    """
    queryset = EventoAgenda.objects.select_related('usuario_creador').order_by('fecha_hora')
    serializer_class = EventoAgendaSerializer

    def perform_create(self, serializer):
        serializer.save(usuario_creador=self.request.user)
