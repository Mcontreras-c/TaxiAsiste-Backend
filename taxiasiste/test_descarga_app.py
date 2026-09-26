import pytest


@pytest.mark.django_db
def test_descarga_app_devuelve_el_link_configurado(autenticar, crear_usuario, settings):
    settings.APK_DOWNLOAD_URL = 'https://expo.dev/artifacts/eas/app.apk'
    resp = autenticar(crear_usuario('desc1', rol_nombre='Central')).get('/api/descarga_app/')
    assert resp.status_code == 200
    assert resp.data == {'url': 'https://expo.dev/artifacts/eas/app.apk'}


@pytest.mark.django_db
def test_descarga_app_sin_link_configurado_devuelve_null(autenticar, crear_usuario, settings):
    settings.APK_DOWNLOAD_URL = ''
    resp = autenticar(crear_usuario('desc2', rol_nombre='Tesorero')).get('/api/descarga_app/')
    assert resp.status_code == 200
    assert resp.data == {'url': None}


@pytest.mark.django_db
def test_descarga_app_requiere_sesion(client):
    assert client.get('/api/descarga_app/').status_code == 401
