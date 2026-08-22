import pytest
from taxiasiste.solicitudes.models import Solicitud


@pytest.fixture
def solicitud_pendiente(db):
    return Solicitud.objects.create(
        origen='Plaza de Armas',
        destino='Aeropuerto',
    )


@pytest.mark.django_db
def test_pendiente_a_asignado_requiere_movil(autenticar, crear_usuario, solicitud_pendiente):
    central = crear_usuario('central1', rol_nombre='Central')
    client = autenticar(central)

    resp = client.post(f'/api/solicitudes/{solicitud_pendiente.id_solicitud}/cambiar_estado/', {'estado': 'ASIGNADO'})

    assert resp.status_code == 400
    assert 'movil' in resp.data['detail'].lower()


@pytest.mark.django_db
def test_pendiente_a_asignado_con_movil_ok(autenticar, crear_usuario, crear_socio, crear_movil, solicitud_pendiente):
    central = crear_usuario('central2', rol_nombre='Central')
    movil = crear_movil(crear_socio('11111111-1'), 'AABB11')
    client = autenticar(central)

    resp = client.post(
        f'/api/solicitudes/{solicitud_pendiente.id_solicitud}/cambiar_estado/',
        {'estado': 'ASIGNADO', 'movil': movil.id_movil},
    )

    assert resp.status_code == 200
    assert resp.data['estado'] == 'ASIGNADO'
    assert resp.data['fecha_asignacion'] is not None


@pytest.mark.django_db
@pytest.mark.parametrize('salto_invalido', ['EN_CURSO', 'COMPLETADO'])
def test_pendiente_no_puede_saltar_directo(autenticar, crear_usuario, solicitud_pendiente, salto_invalido):
    """PENDIENTE solo puede ir a ASIGNADO o CANCELADO — ver TRANSICIONES_VALIDAS."""
    central = crear_usuario('central3', rol_nombre='Central')
    client = autenticar(central)

    resp = client.post(f'/api/solicitudes/{solicitud_pendiente.id_solicitud}/cambiar_estado/', {'estado': salto_invalido})

    assert resp.status_code == 400


@pytest.mark.django_db
def test_completado_es_estado_terminal(autenticar, crear_usuario, solicitud_pendiente):
    """COMPLETADO no tiene transiciones validas de salida — nada puede reabrir un viaje ya cerrado."""
    central = crear_usuario('central4', rol_nombre='Central')
    client = autenticar(central)
    solicitud_pendiente.estado = 'COMPLETADO'
    solicitud_pendiente.save(update_fields=['estado'])

    resp = client.post(f'/api/solicitudes/{solicitud_pendiente.id_solicitud}/cambiar_estado/', {'estado': 'EN_CURSO'})

    assert resp.status_code == 400


@pytest.mark.django_db
def test_cancelar_en_curso_ok(autenticar, crear_usuario, solicitud_pendiente):
    central = crear_usuario('central5', rol_nombre='Central')
    client = autenticar(central)
    solicitud_pendiente.estado = 'EN_CURSO'
    solicitud_pendiente.save(update_fields=['estado'])

    resp = client.post(f'/api/solicitudes/{solicitud_pendiente.id_solicitud}/cambiar_estado/', {'estado': 'CANCELADO'})

    assert resp.status_code == 200
    assert resp.data['fecha_termino'] is not None
