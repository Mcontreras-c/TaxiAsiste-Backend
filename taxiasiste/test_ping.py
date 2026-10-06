"""El health check debe responder a GET y a HEAD (los monitores externos usan HEAD)."""
import pytest


@pytest.mark.django_db
def test_ping_responde_a_get_sin_autenticacion(api_client):
    resp = api_client.get('/api/ping/')
    assert resp.status_code == 200 and resp.data['status'] == 'ok'


@pytest.mark.django_db
def test_ping_responde_a_head_para_los_monitores_de_disponibilidad(api_client):
    assert api_client.head('/api/ping/').status_code == 200
