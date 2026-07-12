from rest_framework.routers import SimpleRouter

from .views import FilaBaseViewSet, MovilViewSet

router = SimpleRouter()
router.register('moviles', MovilViewSet, basename='movil')
router.register('fila-base', FilaBaseViewSet, basename='fila-base')

urlpatterns = router.urls
