from taxiasiste.utils.routers import DecimalPkRouter as SimpleRouter

from .views import RolViewSet, UsuarioViewSet

router = SimpleRouter()
router.register('roles', RolViewSet, basename='rol')
router.register('usuarios', UsuarioViewSet, basename='usuario')

urlpatterns = router.urls
