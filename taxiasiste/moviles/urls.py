from taxiasiste.utils.routers import DecimalPkRouter as SimpleRouter

from .views import FilaBaseViewSet, MovilViewSet, UbicacionActualViewSet

router = SimpleRouter()
router.register('moviles', MovilViewSet, basename='movil')
router.register('fila-base', FilaBaseViewSet, basename='fila-base')
router.register('ubicaciones', UbicacionActualViewSet, basename='ubicacion')

urlpatterns = router.urls
