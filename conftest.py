import pytest


@pytest.fixture(scope='session')
def django_db_setup():
    """
    Reemplaza el setup por defecto de pytest-django (crear una base de test
    nueva + correr migrations) por "no hacer nada": DATABASES['default'] en
    settings_test.py YA apunta al esquema PostgreSQL taxiasiste_test, provisionado
    de antemano con el mismo SQL que taxiasiste_app (ver
    scripts/setup_test_schema.sql). No hay nada que crear ni destruir aca.
    """


@pytest.fixture(autouse=True)
def limpiar_cache():
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def crear_rol(db):
    from taxiasiste.usuarios.models import Rol

    def _crear(nombre_rol):
        rol, _ = Rol.objects.get_or_create(nombre_rol=nombre_rol)
        return rol

    return _crear


@pytest.fixture
def crear_usuario(db, crear_rol):
    from django.contrib.auth.hashers import make_password
    from taxiasiste.usuarios.models import Usuario

    def _crear(username, password='Test2026!', rol_nombre='Conductor', **extra):
        return Usuario.objects.create(
            rol=crear_rol(rol_nombre),
            username=username,
            password_hash=make_password(password),
            fecha_creacion=extra.pop('fecha_creacion', None) or __import__('datetime').date.today(),
            **extra,
        )

    return _crear


@pytest.fixture
def crear_socio(db):
    import datetime
    from taxiasiste.socios.models import Socio

    def _crear(rut, nombre='Juan', apellido='Perez', usuario=None):
        return Socio.objects.create(
            usuario=usuario,
            rut=rut,
            nombre=nombre,
            apellido=apellido,
            fecha_ingreso=datetime.date.today(),
        )

    return _crear


@pytest.fixture
def crear_movil(db):
    import datetime
    from taxiasiste.moviles.models import Movil

    def _crear(socio, patente, **extra):
        return Movil.objects.create(
            socio=socio,
            patente=patente,
            fecha_registro=extra.pop('fecha_registro', None) or datetime.date.today(),
            **extra,
        )

    return _crear


@pytest.fixture
def autenticar(api_client):
    """Fija el header Authorization simulando un login real: arma el mismo JWT
    (con claim 'sid') que emite LoginView, sin pasar por el endpoint HTTP."""

    def _autenticar(usuario, sid='test-sid', confirmar=True):
        import uuid
        from rest_framework_simplejwt.tokens import RefreshToken

        usuario.sesion_actual = sid or uuid.uuid4().hex
        usuario.save(update_fields=['sesion_actual'])

        refresh = RefreshToken()
        refresh['user_id'] = usuario.id_usuario
        refresh['username'] = usuario.username
        refresh['rol'] = usuario.rol.nombre_rol
        refresh['sid'] = usuario.sesion_actual
        credenciales = {'HTTP_AUTHORIZATION': f'Bearer {refresh.access_token}'}
        if confirmar:
            # Por defecto ya confirmo su clave (acciones sensibles); confirmar=False para probar sin ella.
            from taxiasiste.usuarios.confirmacion import emitir_token
            credenciales['HTTP_X_CONFIRMACION'] = emitir_token(usuario)
        api_client.credentials(**credenciales)
        return api_client

    return _autenticar
