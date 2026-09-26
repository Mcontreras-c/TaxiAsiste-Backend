from taxiasiste.utils.routers import DecimalPkRouter as SimpleRouter

from .views import PasajeroViewSet, SolicitudViewSet
from .views_reservas import ReservaViewSet

router = SimpleRouter()
router.register('pasajeros', PasajeroViewSet, basename='pasajero')
router.register('solicitudes', SolicitudViewSet, basename='solicitud')
router.register('reservas', ReservaViewSet, basename='reserva')

urlpatterns = router.urls
