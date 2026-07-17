from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    HistorialEventoViewSet,
    dashboard,
    solicitudes_por_estado,
    socios_bloqueados,
    cuotas_vencidas,
)

router = SimpleRouter()
router.register('historial', HistorialEventoViewSet, basename='historial')

urlpatterns = router.urls + [
    path('reportes/dashboard/', dashboard, name='dashboard'),
    path('reportes/solicitudes_por_estado/', solicitudes_por_estado, name='solicitudes-por-estado'),
    path('reportes/socios_bloqueados/', socios_bloqueados, name='socios-bloqueados'),
    path('reportes/cuotas_vencidas/', cuotas_vencidas, name='cuotas-vencidas'),
]
