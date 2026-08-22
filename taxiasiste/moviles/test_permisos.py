import pytest


@pytest.mark.django_db
def test_conductor_puede_conectar_su_propio_movil(autenticar, crear_usuario, crear_socio, crear_movil):
    conductor = crear_usuario('conductorDueno', rol_nombre='Conductor')
    movil = crear_movil(crear_socio('77777777-7', usuario=conductor), 'DDDD44')
    client = autenticar(conductor)

    resp = client.post(f'/api/moviles/{movil.id_movil}/conectar/')

    assert resp.status_code == 200
    assert resp.data['estado_operativo'] == 'DISPONIBLE'


@pytest.mark.django_db
def test_conductor_no_puede_operar_movil_ajeno(autenticar, crear_usuario, crear_socio, crear_movil):
    conductor = crear_usuario('conductorAjeno', rol_nombre='Conductor')
    crear_socio('88888888-8', usuario=conductor)  # sin movil propio
    otro_movil = crear_movil(crear_socio('99999999-9'), 'EEEE55')
    client = autenticar(conductor)

    resp = client.post(f'/api/moviles/{otro_movil.id_movil}/conectar/')

    assert resp.status_code == 403


@pytest.mark.django_db
def test_central_puede_operar_cualquier_movil(autenticar, crear_usuario, crear_socio, crear_movil):
    central = crear_usuario('centralOperando', rol_nombre='Central')
    movil = crear_movil(crear_socio('10101010-1'), 'FFFF66')
    client = autenticar(central)

    resp = client.post(f'/api/moviles/{movil.id_movil}/desconectar/')

    assert resp.status_code == 200
    assert resp.data['estado_operativo'] == 'INACTIVO'


@pytest.mark.django_db
def test_paletero_no_puede_operar_moviles(autenticar, crear_usuario, crear_socio, crear_movil):
    paletero = crear_usuario('paleteroX', rol_nombre='Paletero')
    movil = crear_movil(crear_socio('12121212-1'), 'GGGG77')
    client = autenticar(paletero)

    resp = client.post(f'/api/moviles/{movil.id_movil}/conectar/')

    assert resp.status_code == 403


@pytest.mark.django_db
def test_cualquier_autenticado_puede_listar_moviles(autenticar, crear_usuario, crear_socio, crear_movil):
    """Lectura es libre para cualquier rol autenticado (ver EsPropietarioDelMovilOStaff) —
    Central necesita ver todos los moviles en su mapa."""
    paletero = crear_usuario('paleteroLector', rol_nombre='Paletero')
    crear_movil(crear_socio('13131313-1'), 'HHHH88')
    client = autenticar(paletero)

    resp = client.get('/api/moviles/')

    assert resp.status_code == 200
