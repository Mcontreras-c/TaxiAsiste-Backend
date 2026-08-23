import pytest
from taxiasiste.solicitudes.models import Solicitud


@pytest.fixture
def solicitud_pendiente(db):
    return Solicitud.objects.create(
        origen='Plaza de Armas',
        destino='Aeropuerto',
    )


@pytest.fixture
def solicitud_asignada(solicitud_pendiente, crear_socio, crear_movil):
    movil = crear_movil(crear_socio('20202020-2'), 'ASIG01')
    solicitud_pendiente.movil = movil
    solicitud_pendiente.estado = 'ASIGNADO'
    solicitud_pendiente.save(update_fields=['movil', 'estado'])
    return solicitud_pendiente


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


@pytest.mark.django_db
def test_en_curso_pone_el_movil_en_servicio(autenticar, crear_usuario, solicitud_asignada):
    """El mapa de Central pinta EN_SERVICIO de azul (COLOR_ESTADO en
    MapaDespacho.tsx) -- sin este flag, el pasajero a bordo nunca se refleja
    ahi aunque el viaje ya haya arrancado."""
    central = crear_usuario('central6', rol_nombre='Central')
    client = autenticar(central)
    assert solicitud_asignada.movil.estado_operativo == 'DISPONIBLE'

    resp = client.post(f'/api/solicitudes/{solicitud_asignada.id_solicitud}/cambiar_estado/', {'estado': 'EN_CURSO'})

    assert resp.status_code == 200
    solicitud_asignada.movil.refresh_from_db()
    assert solicitud_asignada.movil.estado_operativo == 'EN_SERVICIO'


@pytest.mark.django_db
def test_en_curso_no_pisa_un_movil_bloqueado_o_inactivo(autenticar, crear_usuario, solicitud_asignada):
    """Si Central bloqueo/desconecto el movil mientras la solicitud seguia
    ASIGNADO, pasar a EN_CURSO no debe reactivarlo poniendolo EN_SERVICIO."""
    central = crear_usuario('central7', rol_nombre='Central')
    client = autenticar(central)
    solicitud_asignada.movil.estado_operativo = 'BLOQUEADO'
    solicitud_asignada.movil.save(update_fields=['estado_operativo'])

    client.post(f'/api/solicitudes/{solicitud_asignada.id_solicitud}/cambiar_estado/', {'estado': 'EN_CURSO'})

    solicitud_asignada.movil.refresh_from_db()
    assert solicitud_asignada.movil.estado_operativo == 'BLOQUEADO'


@pytest.mark.django_db
@pytest.mark.parametrize('estado_final', ['COMPLETADO', 'CANCELADO'])
def test_terminar_viaje_vuelve_el_movil_a_disponible(autenticar, crear_usuario, solicitud_asignada, estado_final):
    central = crear_usuario(f'central8{estado_final}', rol_nombre='Central')
    client = autenticar(central)
    client.post(f'/api/solicitudes/{solicitud_asignada.id_solicitud}/cambiar_estado/', {'estado': 'EN_CURSO'})
    solicitud_asignada.movil.refresh_from_db()
    assert solicitud_asignada.movil.estado_operativo == 'EN_SERVICIO'

    client.post(f'/api/solicitudes/{solicitud_asignada.id_solicitud}/cambiar_estado/', {'estado': estado_final})

    solicitud_asignada.movil.refresh_from_db()
    assert solicitud_asignada.movil.estado_operativo == 'DISPONIBLE'


@pytest.mark.django_db
def test_cancelar_desde_asignado_no_toca_el_movil(autenticar, crear_usuario, solicitud_asignada):
    """Cancelar antes de EN_CURSO: el movil nunca paso a EN_SERVICIO, asi
    que tampoco hay nada que revertir -- sigue DISPONIBLE como estaba."""
    central = crear_usuario('central9', rol_nombre='Central')
    client = autenticar(central)

    client.post(f'/api/solicitudes/{solicitud_asignada.id_solicitud}/cambiar_estado/', {'estado': 'CANCELADO'})

    solicitud_asignada.movil.refresh_from_db()
    assert solicitud_asignada.movil.estado_operativo == 'DISPONIBLE'
