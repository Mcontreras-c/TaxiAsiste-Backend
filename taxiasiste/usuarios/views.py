from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from .models import Rol, Usuario
from .serializers import RolSerializer, UsuarioSerializer


class RolViewSet(ReadOnlyModelViewSet):
    """Listado y detalle de roles. Solo lectura."""
    queryset = Rol.objects.filter(activo=True)
    serializer_class = RolSerializer


class UsuarioViewSet(ModelViewSet):
    queryset = Usuario.objects.select_related('rol').all()
    serializer_class = UsuarioSerializer

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Devuelve el perfil del usuario autenticado (por username del token JWT)."""
        try:
            usuario = Usuario.objects.select_related('rol').get(
                username=request.user.username
            )
        except Usuario.DoesNotExist:
            return Response(
                {'detail': 'Perfil de usuario no encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = UsuarioSerializer(usuario)
        return Response(serializer.data)
