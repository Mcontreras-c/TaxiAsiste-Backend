import pytest


@pytest.mark.django_db
def test_refresh_rota_y_devuelve_un_refresh_nuevo(api_client, crear_usuario):
    crear_usuario('conductorRot', password='Clave123!')
    login = api_client.post('/api/login/', {'username': 'conductorRot', 'password': 'Clave123!'})
    refresh_viejo = login.data['refresh']

    resp = api_client.post('/api/token/refresh/', {'refresh': refresh_viejo})

    assert resp.status_code == 200
    assert 'access' in resp.data
    assert 'refresh' in resp.data
    assert resp.data['refresh'] != refresh_viejo


@pytest.mark.django_db
def test_refresh_usado_no_sirve_una_segunda_vez(api_client, crear_usuario):
    """ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION: el refresh token
    queda en blacklist apenas se usa una vez -- si alguien lo intercepta y
    ya se uso, no le sirve."""
    crear_usuario('conductorReuso', password='Clave123!')
    login = api_client.post('/api/login/', {'username': 'conductorReuso', 'password': 'Clave123!'})
    refresh_original = login.data['refresh']

    primero = api_client.post('/api/token/refresh/', {'refresh': refresh_original})
    segundo = api_client.post('/api/token/refresh/', {'refresh': refresh_original})

    assert primero.status_code == 200
    assert segundo.status_code == 401


@pytest.mark.django_db
def test_logout_invalida_el_refresh_token_de_inmediato(api_client, crear_usuario):
    crear_usuario('conductorLogout', password='Clave123!')
    login = api_client.post('/api/login/', {'username': 'conductorLogout', 'password': 'Clave123!'})
    refresh = login.data['refresh']

    logout = api_client.post('/api/logout/', {'refresh': refresh})
    intento_post_logout = api_client.post('/api/token/refresh/', {'refresh': refresh})

    assert logout.status_code == 205
    assert intento_post_logout.status_code == 401


@pytest.mark.django_db
def test_logout_sin_refresh_devuelve_400(api_client):
    resp = api_client.post('/api/logout/', {})

    assert resp.status_code == 400


@pytest.mark.django_db
def test_logout_con_token_ya_invalido_no_revienta(api_client):
    """Un refresh malformado/ya vencido no debe hacer que /api/logout/ falle
    con un 500 -- el resultado que le importa al cliente (que ese token no
    sirva) ya se cumple igual."""
    resp = api_client.post('/api/logout/', {'refresh': 'esto-no-es-un-jwt-valido'})

    assert resp.status_code == 205
