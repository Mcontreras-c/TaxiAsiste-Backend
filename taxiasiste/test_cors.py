import pytest


def _preflight(client, ruta, cabeceras):
    return client.options(
        ruta,
        HTTP_ORIGIN='http://localhost:5173',
        HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS=cabeceras,
    )


@pytest.mark.django_db
def test_el_navegador_puede_mandar_la_cabecera_de_confirmacion(client):
    """Sin esto el panel web no puede dar de baja ni editar: el navegador bloquea la peticion
    real despues del preflight (las pruebas con el cliente de Django no pasan por CORS)."""
    resp = _preflight(client, '/api/usuarios/1/dar_de_baja/', 'authorization,content-type,x-confirmacion')

    permitidas = resp['access-control-allow-headers'].lower().replace(' ', '').split(',')
    assert resp.status_code == 200
    assert 'x-confirmacion' in permitidas
    assert 'authorization' in permitidas and 'content-type' in permitidas


@pytest.mark.django_db
def test_no_se_abren_cabeceras_de_mas(client):
    resp = _preflight(client, '/api/usuarios/1/dar_de_baja/', 'authorization')

    permitidas = resp['access-control-allow-headers'].lower().replace(' ', '').split(',')
    assert 'x-secreto-inventado' not in permitidas
