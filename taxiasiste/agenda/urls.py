from taxiasiste.utils.routers import DecimalPkRouter as SimpleRouter

from .views import DocumentoAgendaViewSet, EventoAgendaViewSet

router = SimpleRouter()
router.register('eventos-agenda', EventoAgendaViewSet, basename='evento-agenda')
router.register('documentos-agenda', DocumentoAgendaViewSet, basename='documento-agenda')

urlpatterns = router.urls
