from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from taxiasiste.login import LoginView, LogoutView
from taxiasiste.views import geocodificar, ping, ruta

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/login/', LoginView.as_view(), name='login'),
    path('api/logout/', LogoutView.as_view(), name='logout'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/ping/', ping, name='ping'),
    path('api/geocodificar/', geocodificar, name='geocodificar'),
    path('api/ruta/', ruta, name='ruta'),
    path('api/', include('taxiasiste.usuarios.urls')),
    path('api/', include('taxiasiste.socios.urls')),
    path('api/', include('taxiasiste.moviles.urls')),
    path('api/', include('taxiasiste.solicitudes.urls')),
    path('api/', include('taxiasiste.reportes.urls')),
    path('api/', include('taxiasiste.agenda.urls')),
]

if settings.DEBUG:
    # En produccion esto lo sirve nginx directo (alias /media/) -- ver
    # project_vps_infra en las notas del servidor cuando se despliegue.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
