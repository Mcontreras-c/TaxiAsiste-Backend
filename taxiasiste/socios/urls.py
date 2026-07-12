from rest_framework.routers import SimpleRouter

from .views import BloqueoViewSet, CuotaViewSet, SocioViewSet

router = SimpleRouter()
router.register('socios', SocioViewSet, basename='socio')
router.register('cuotas', CuotaViewSet, basename='cuota')
router.register('bloqueos', BloqueoViewSet, basename='bloqueo')

urlpatterns = router.urls
