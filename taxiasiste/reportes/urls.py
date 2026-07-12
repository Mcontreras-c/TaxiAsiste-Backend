from rest_framework.routers import SimpleRouter

from .views import HistorialEventoViewSet

router = SimpleRouter()
router.register('historial', HistorialEventoViewSet, basename='historial')

urlpatterns = router.urls
