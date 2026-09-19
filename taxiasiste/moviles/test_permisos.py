import pytest
from taxiasiste.solicitudes.models import Solicitud


@pytest.mark.django_db
def test_conductor_puede_conectar_su_propio_movil(autenticar, crear_usuario, crear_socio, crear_movil):
    conductor = crear_usuario('conductorDueno', rol_nombre='Conductor')
    movil = crear_movil(crear_socio('77777777-7', usuario=conductor), 'DDDD44')
    client = autenticar(conductor)

    resp = client.post(f'/api/moviles/{movil.id_movil}/conectar/')

    assert resp.status_code == 200
    assert resp.data['estado_operativo'] == 'DISPONIBLE'


@pytest.mark.django_db
def test_conectar_pone_en_viaje_si_hay_viaje_en_curso(autenticar, crear_usuario, crear_socio, crear_movil):
    """ConductorProvider (Mobile) llama a /conectar/ cada vez que arranca la
    app, sea login o simplemente reabrirla. Si el conductor lo hace en medio
    de un viaje EN_CURSO, esto no puede pisarle el EN_VIAJE que puso
    cambiar_estado -- si no, el mapa de Central lo vuelve a mostrar libre
    con un pasajero a bordo."""
    conductor = crear_usuario('conductorEnViaje', rol_nombre='Conductor')
    movil = crear_movil(crear_socio('14141414-1', usuario=conductor), 'IIII99', estado_operativo='EN_VIAJE')
    Solicitud.objects.create(movil=movil, origen='Plaza de Armas', destino='Aeropuerto', estado='EN_CURSO')
    client = autenticar(conductor)

    resp = client.post(f'/api/moviles/{movil.id_movil}/conectar/')

    assert resp.status_code == 200
    assert resp.data['estado_operativo'] == 'EN_VIAJE'


@pytest.mark.django_db
def test_conectar_pone_en_servicio_si_hay_viaje_asignado(autenticar, crear_usuario, crear_socio, crear_movil):
    """Igual que el test anterior pero para un viaje ASIGNADO (el conductor
    ya lo tomo pero todavia no llega al pasajero) -- reconectar no debe
    bajarlo a DISPONIBLE."""
    conductor = crear_usuario('conductorAsignado', rol_nombre='Conductor')
    movil = crear_movil(crear_socio('16161616-1', usuario=conductor), 'KKKK11', estado_operativo='EN_SERVICIO')
    Solicitud.objects.create(movil=movil, origen='Plaza de Armas', destino='Aeropuerto', estado='ASIGNADO')
    client = autenticar(conductor)

    resp = client.post(f'/api/moviles/{movil.id_movil}/conectar/')

    assert resp.status_code == 200
    assert resp.data['estado_operativo'] == 'EN_SERVICIO'


@pytest.mark.django_db
def test_conectar_pone_disponible_si_no_hay_viaje_en_curso(autenticar, crear_usuario, crear_socio, crear_movil):
    """Un viaje ya COMPLETADO/CANCELADO no debe seguir bloqueando el reset a
    DISPONIBLE -- solo ASIGNADO/EN_CURSO cuenta."""
    conductor = crear_usuario('conductorViajeViejo', rol_nombre='Conductor')
    movil = crear_movil(crear_socio('15151515-1', usuario=conductor), 'JJJJ00', estado_operativo='EN_VIAJE')
    Solicitud.objects.create(movil=movil, origen='Plaza de Armas', destino='Aeropuerto', estado='COMPLETADO')
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
