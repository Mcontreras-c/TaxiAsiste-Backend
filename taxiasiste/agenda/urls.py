from taxiasiste.utils.routers import DecimalPkRouter as SimpleRouter

from .views import EventoAgendaViewSet

router = SimpleRouter()
router.register('eventos-agenda', EventoAgendaViewSet, basename='evento-agenda')

urlpatterns = router.urls
