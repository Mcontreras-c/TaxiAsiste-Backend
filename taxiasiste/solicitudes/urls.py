from rest_framework.routers import SimpleRouter

from .views import PasajeroViewSet, SolicitudViewSet

router = SimpleRouter()
router.register('pasajeros', PasajeroViewSet, basename='pasajero')
router.register('solicitudes', SolicitudViewSet, basename='solicitud')

urlpatterns = router.urls
