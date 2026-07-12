from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from .models import Rol, Usuario
from .serializers import RolSerializer, UsuarioSerializer


class RolViewSet(ReadOnlyModelViewSet):
    queryset = Rol.objects.filter(activo=1)
    serializer_class = RolSerializer


class UsuarioViewSet(ModelViewSet):
    queryset = Usuario.objects.select_related('rol').all()
    serializer_class = UsuarioSerializer

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Devuelve el perfil del usuario autenticado. request.user ya es un Usuario de Oracle."""
        serializer = UsuarioSerializer(request.user)
        return Response(serializer.data)
