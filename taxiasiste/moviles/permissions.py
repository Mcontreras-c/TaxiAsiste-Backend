from rest_framework.permissions import SAFE_METHODS, BasePermission

ROLES_STAFF = {'Administrador', 'Central'}


class EsPropietarioDelMovilOStaff(BasePermission):
    """
    Lectura (GET/list/retrieve): cualquier usuario autenticado — Central
    necesita ver todos los moviles en su panel/mapa, y el propio conductor
    necesita poder listar para ubicar el suyo.

    Escritura (POST de las acciones ubicacion/conectar/desconectar, y
    PATCH/PUT/DELETE genericos del ModelViewSet):
    - Administrador / Central: pueden operar sobre cualquier movil (gestion).
    - Conductor: solo sobre el movil vinculado a su propio Socio.
    - Cualquier otro rol (Tesorero, Paletero): sin permiso de escritura aqui.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        rol = getattr(getattr(request.user, 'rol', None), 'nombre_rol', None)
        if rol in ROLES_STAFF:
            return True
        if rol == 'Conductor':
            # Se autoriza a nivel de vista; el objeto especifico se valida
            # en has_object_permission (necesita saber a que movil se refiere).
            return True
        return False

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        rol = getattr(getattr(request.user, 'rol', None), 'nombre_rol', None)
        if rol in ROLES_STAFF:
            return True
        if rol == 'Conductor':
            socio = getattr(request.user, 'socio', None)
            return socio is not None and obj.socio_id == socio.id_socio
        return False
