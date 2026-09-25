import pytest


@pytest.mark.django_db
def test_dashboard_cuenta_en_servicio_y_en_viaje_como_moviles_ocupados(
    autenticar, crear_usuario, crear_socio, crear_movil
):
    """EN_VIAJE (pasajero a bordo) se agrego despues de EN_SERVICIO; si el
    resumen solo contara EN_SERVICIO, un movil con el pasajero a bordo
    desapareceria del panel y de su total."""
    central = crear_usuario('centralDash1', rol_nombre='Central')
    crear_movil(crear_socio('50505050-5'), 'DASH01', estado_operativo='EN_SERVICIO')
    crear_movil(crear_socio('51515151-5'), 'DASH02', estado_operativo='EN_VIAJE')
    crear_movil(crear_socio('52525252-5'), 'DASH03', estado_operativo='DISPONIBLE')
    crear_movil(crear_socio('53535353-5'), 'DASH04', estado_operativo='BLOQUEADO')
    client = autenticar(central)

    resp = client.get('/api/reportes/dashboard/')

    assert resp.status_code == 200
    assert resp.data['moviles']['en_servicio'] == 2
    assert resp.data['moviles']['disponibles'] == 1
