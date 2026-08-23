import pytest


@pytest.mark.django_db
def test_refresh_no_rota_y_se_puede_reusar(api_client, crear_usuario):
    """ROTATE_REFRESH_TOKENS se probo y se descarto (ver settings.py):
    con varios pollers concurrentes compartiendo el mismo refresh token,
    rotarlo en cada uso rompia el GPS en background cada vez que dos
    pollers refrescaban casi al mismo tiempo. El mismo refresh token tiene
    que poder reusarse durante toda su vida util."""
    crear_usuario('conductorReuso', password='Clave123!')
    login = api_client.post('/api/login/', {'username': 'conductorReuso', 'password': 'Clave123!'})
    refresh = login.data['refresh']

    primero = api_client.post('/api/token/refresh/', {'refresh': refresh})
    segundo = api_client.post('/api/token/refresh/', {'refresh': refresh})

    assert primero.status_code == 200
    assert segundo.status_code == 200
    assert 'refresh' not in primero.data


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
