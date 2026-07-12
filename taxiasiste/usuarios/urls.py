from rest_framework.routers import SimpleRouter

from .views import RolViewSet, UsuarioViewSet

router = SimpleRouter()
router.register('roles', RolViewSet, basename='rol')
router.register('usuarios', UsuarioViewSet, basename='usuario')

urlpatterns = router.urls
