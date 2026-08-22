import pytest


@pytest.mark.django_db
def test_login_ok_devuelve_tokens(api_client, crear_usuario):
    crear_usuario('conductor1', password='Clave123!', rol_nombre='Conductor')

    resp = api_client.post('/api/login/', {'username': 'conductor1', 'password': 'Clave123!'})

    assert resp.status_code == 200
    assert 'access' in resp.data
    assert 'refresh' in resp.data
    assert resp.data['usuario']['rol'] == 'Conductor'


@pytest.mark.django_db
def test_login_password_incorrecta_devuelve_401(api_client, crear_usuario):
    crear_usuario('conductor2', password='Clave123!')

    resp = api_client.post('/api/login/', {'username': 'conductor2', 'password': 'otra'})

    assert resp.status_code == 401


@pytest.mark.django_db
def test_login_usuario_inexistente_devuelve_401(api_client):
    resp = api_client.post('/api/login/', {'username': 'no_existe', 'password': 'x'})

    assert resp.status_code == 401


@pytest.mark.django_db
def test_login_usuario_bloqueado_devuelve_403(api_client, crear_usuario):
    crear_usuario('conductor3', password='Clave123!', estado='BLOQUEADO')

    resp = api_client.post('/api/login/', {'username': 'conductor3', 'password': 'Clave123!'})

    assert resp.status_code == 403


@pytest.mark.django_db
def test_login_nuevo_invalida_sesion_anterior(api_client, crear_usuario):
    """Sesion unica (ver authentication.py): loguearse de nuevo debe dejar
    inservible cualquier token viejo, incluso si todavia no vencio."""
    usuario = crear_usuario('conductor4', password='Clave123!')

    primer_login = api_client.post('/api/login/', {'username': 'conductor4', 'password': 'Clave123!'})
    token_viejo = primer_login.data['access']

    api_client.post('/api/login/', {'username': 'conductor4', 'password': 'Clave123!'})

    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token_viejo}')
    resp = api_client.get('/api/usuarios/me/')

    assert resp.status_code == 401
