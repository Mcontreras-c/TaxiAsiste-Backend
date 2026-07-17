from rest_framework.routers import SimpleRouter

from .views import BloqueoViewSet, CuotaViewSet, SocioViewSet, TesoreriaMovimientoViewSet

router = SimpleRouter()
router.register('socios', SocioViewSet, basename='socio')
router.register('cuotas', CuotaViewSet, basename='cuota')
router.register('bloqueos', BloqueoViewSet, basename='bloqueo')
router.register('tesoreria', TesoreriaMovimientoViewSet, basename='tesoreria')

urlpatterns = router.urls
