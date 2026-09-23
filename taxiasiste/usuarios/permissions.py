from rest_framework.permissions import BasePermission


class EsAdministrador(BasePermission):
    """Solo el rol Administrador tiene permiso (sin excepcion para lectura)."""

    def has_permission(self, request, view):
        rol = getattr(getattr(request.user, 'rol', None), 'nombre_rol', None)
        return rol == 'Administrador'
