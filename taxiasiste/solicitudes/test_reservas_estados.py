import datetime

import pytest

from taxiasiste.solicitudes.models import Pasajero, Reserva, ReservaEvento
# Fixtures y utilidades compartidas con test_reservas.py
from taxiasiste.solicitudes.test_reservas import DURACION, _google_ok, _t, conductor, crear_reserva  # noqa: F401


@pytest.fixture
def pasajero(db):
    return Pasajero.objects.create(rut='7777777-7', nombre='Rosa', apellido='Vega', fecha_registro=datetime.date.today())


def _asignada(crear_reserva, movil, minutos, estado='ASIGNADA', **extra):
    """Reserva ya asignada a un movil (evita pasar por 'tomar', que valida horarios)."""
    return crear_reserva(minutos, movil=movil, estado=estado, **extra)


# ----------------------------------------------------------------- en camino

@pytest.mark.django_db
def test_no_se_puede_salir_con_demasiada_anticipacion(autenticar, conductor, crear_reserva):
    usuario, movil = conductor('cond_e1', 'EST001', '11000000-1')
    reserva = _asignada(crear_reserva, movil, 180)
    resp = autenticar(usuario).post(f'/api/reservas/{reserva.pk}/en_camino/')
    assert resp.status_code == 409
    assert 'pronto' in resp.data['detail']


@pytest.mark.django_db
def test_en_camino_pone_el_movil_en_servicio(autenticar, conductor, crear_reserva):
    usuario, movil = conductor('cond_e2', 'EST002', '12000000-2')
    reserva = _asignada(crear_reserva, movil, 50)

    resp = autenticar(usuario).post(f'/api/reservas/{reserva.pk}/en_camino/')

    assert resp.status_code == 200, resp.data
    reserva.refresh_from_db(); movil.refresh_from_db()
    assert reserva.estado == 'EN_CAMINO'
    assert movil.estado_operativo == 'EN_SERVICIO'
    assert ReservaEvento.objects.filter(reserva=reserva, tipo='EN_CAMINO').exists()


@pytest.mark.django_db
def test_no_puede_salir_a_una_reserva_ajena(autenticar, conductor, crear_reserva):
    _, movil = conductor('cond_e3', 'EST003', '13000000-3')
    otro, _ = conductor('cond_e4', 'EST004', '14000000-4')
    reserva = _asignada(crear_reserva, movil, 50)
    assert autenticar(otro).post(f'/api/reservas/{reserva.pk}/en_camino/').status_code == 403


# ------------------------------------------------------------------ completar

@pytest.mark.django_db
def test_completar_libera_al_movil(autenticar, conductor, crear_reserva):
    usuario, movil = conductor('cond_c1', 'EST005', '15000000-5')
    reserva = _asignada(crear_reserva, movil, 50)
    cliente = autenticar(usuario)
    cliente.post(f'/api/reservas/{reserva.pk}/en_camino/')

    resp = cliente.post(f'/api/reservas/{reserva.pk}/completar/')

    assert resp.status_code == 200
    reserva.refresh_from_db(); movil.refresh_from_db()
    assert reserva.estado == 'COMPLETADA' and reserva.fecha_termino is not None
    assert movil.estado_operativo == 'DISPONIBLE'


@pytest.mark.django_db
def test_no_se_completa_sin_haber_salido(autenticar, conductor, crear_reserva):
    usuario, movil = conductor('cond_c2', 'EST006', '16000000-6')
    reserva = _asignada(crear_reserva, movil, 50)
    assert autenticar(usuario).post(f'/api/reservas/{reserva.pk}/completar/').status_code == 409


# ---------------------------------------------------------- pasajero ausente

@pytest.mark.django_db
def test_pasajero_ausente_exige_esperar_10_minutos(autenticar, conductor, crear_reserva, pasajero):
    usuario, movil = conductor('cond_p1', 'EST007', '17000000-7')
    reserva = _asignada(crear_reserva, movil, 3, estado='EN_CAMINO', pasajero=pasajero)  # recogida en 3 min
    resp = autenticar(usuario).post(f'/api/reservas/{reserva.pk}/pasajero_ausente/')
    assert resp.status_code == 409
    assert 'Espera al pasajero' in resp.data['detail']


@pytest.mark.django_db
def test_pasajero_ausente_suma_un_incumplimiento(autenticar, conductor, crear_reserva, pasajero):
    usuario, movil = conductor('cond_p2', 'EST008', '18000000-8')
    reserva = _asignada(crear_reserva, movil, -15, estado='EN_CAMINO', pasajero=pasajero)

    resp = autenticar(usuario).post(f'/api/reservas/{reserva.pk}/pasajero_ausente/')

    assert resp.status_code == 200, resp.data
    assert resp.data['estado'] == 'PASAJERO_AUSENTE'
    assert resp.data['pasajero_bloqueado'] is False
    pasajero.refresh_from_db()
    assert pasajero.incumplimientos == 1 and pasajero.bloqueado_domicilio == 0


@pytest.mark.django_db
def test_a_la_tercera_vez_el_pasajero_queda_bloqueado(autenticar, conductor, crear_reserva, pasajero):
    usuario, movil = conductor('cond_p3', 'EST009', '19000000-9')
    cliente = autenticar(usuario)
    ultimo = None
    for _ in range(3):
        reserva = _asignada(crear_reserva, movil, -15, estado='EN_CAMINO', pasajero=pasajero)
        ultimo = cliente.post(f'/api/reservas/{reserva.pk}/pasajero_ausente/')

    assert ultimo.data['pasajero_bloqueado'] is True
    pasajero.refresh_from_db()
    assert pasajero.incumplimientos == 3 and pasajero.bloqueado_domicilio == 1


@pytest.mark.django_db
def test_pasajero_bloqueado_no_puede_reservar(autenticar, crear_usuario, pasajero, monkeypatch):
    monkeypatch.setattr('taxiasiste.views.requests.get', _google_ok())
    pasajero.bloqueado_domicilio = 1
    pasajero.save(update_fields=['bloqueado_domicilio'])
    central = crear_usuario('cen_b1', rol_nombre='Central')

    resp = autenticar(central).post('/api/reservas/', {
        'origen': 'Av. Falsa 123', 'fecha_hora_recogida': _t(180).isoformat(), 'pasajero': pasajero.pk,
    })

    assert resp.status_code == 409
    assert 'no puede pedir móviles a domicilio' in resp.data['detail']


@pytest.mark.django_db
def test_pasajero_bloqueado_no_puede_pedir_movil_por_telefono(autenticar, crear_usuario, pasajero, monkeypatch):
    monkeypatch.setattr('taxiasiste.views.requests.get', _google_ok())
    pasajero.bloqueado_domicilio = 1
    pasajero.save(update_fields=['bloqueado_domicilio'])
    central = crear_usuario('cen_b2', rol_nombre='Central')

    resp = autenticar(central).post('/api/solicitudes/', {
        'origen': 'Av. Falsa 123', 'pasajero': pasajero.pk, 'canal_entrada': 'TELEFONO',
    })

    assert resp.status_code == 400
    assert 'no puede pedir móviles a domicilio' in str(resp.data)


@pytest.mark.django_db
def test_pasajero_bloqueado_si_puede_tomar_uno_en_el_hospital(autenticar, crear_usuario, pasajero, monkeypatch):
    monkeypatch.setattr('taxiasiste.views.requests.get', _google_ok())
    pasajero.bloqueado_domicilio = 1
    pasajero.save(update_fields=['bloqueado_domicilio'])
    central = crear_usuario('cen_b3', rol_nombre='Central')

    resp = autenticar(central).post('/api/solicitudes/', {
        'origen': 'Hospital Félix Bulnes', 'pasajero': pasajero.pk, 'canal_entrada': 'PRESENCIAL',
    })

    assert resp.status_code == 201, resp.data


@pytest.mark.django_db
def test_solo_un_administrador_levanta_el_bloqueo(autenticar, crear_usuario, pasajero):
    pasajero.incumplimientos, pasajero.bloqueado_domicilio = 3, 1
    pasajero.save(update_fields=['incumplimientos', 'bloqueado_domicilio'])

    assert autenticar(crear_usuario('cen_b4', rol_nombre='Central')).post(
        f'/api/pasajeros/{pasajero.pk}/levantar_bloqueo/').status_code == 403
    resp = autenticar(crear_usuario('adm_b5', rol_nombre='Administrador')).post(
        f'/api/pasajeros/{pasajero.pk}/levantar_bloqueo/')

    assert resp.status_code == 200
    pasajero.refresh_from_db()
    assert pasajero.incumplimientos == 0 and pasajero.bloqueado_domicilio == 0


@pytest.mark.django_db
def test_el_pasajero_no_puede_editar_su_propio_bloqueo(autenticar, crear_usuario, pasajero):
    central = crear_usuario('cen_b6', rol_nombre='Central')
    pasajero.bloqueado_domicilio = 1
    pasajero.save(update_fields=['bloqueado_domicilio'])
    autenticar(central).patch(f'/api/pasajeros/{pasajero.pk}/', {'bloqueado_domicilio': 0, 'incumplimientos': 0})
    pasajero.refresh_from_db()
    assert pasajero.bloqueado_domicilio == 1


# -------------------------------------------------------------------- alertas

@pytest.mark.django_db
def test_alerta_sin_conductor_cuando_ya_falta_poco(autenticar, crear_usuario, crear_reserva):
    lejana = crear_reserva(300)   # faltan horas: sin alerta
    cercana = crear_reserva(50)   # hora maxima de salida en 15 min (< 30): alerta
    resp = autenticar(crear_usuario('cen_a1', rol_nombre='Central')).get('/api/reservas/')
    alertas = {r['folio']: r['alerta'] for r in resp.data}
    assert alertas[lejana.folio] is None
    assert alertas[cercana.folio] == 'SIN_CONDUCTOR'


@pytest.mark.django_db
def test_alerta_no_confirmada_si_el_conductor_no_salio(autenticar, crear_usuario, conductor, crear_reserva):
    _, movil = conductor('cond_a2', 'EST010', '21000000-1')
    # recogida en 25 min -> hora maxima de salida hace 10 min (> tolerancia de 5)
    sin_confirmar = _asignada(crear_reserva, movil, 25)
    a_tiempo = _asignada(crear_reserva, movil, 180)
    resp = autenticar(crear_usuario('cen_a2', rol_nombre='Central')).get('/api/reservas/')
    alertas = {r['folio']: r['alerta'] for r in resp.data}
    assert alertas[sin_confirmar.folio] == 'NO_CONFIRMADA'
    assert alertas[a_tiempo.folio] is None


# -------------------------------------------------------------------- liberar

@pytest.mark.django_db
def test_central_libera_y_registra_el_incumplimiento(autenticar, crear_usuario, conductor, crear_reserva):
    _, movil = conductor('cond_l1', 'EST011', '22000000-2')
    reserva = _asignada(crear_reserva, movil, 25)
    central = autenticar(crear_usuario('cen_l1', rol_nombre='Central'))

    resp = central.post(f'/api/reservas/{reserva.pk}/liberar/', {'incumplio': True, 'motivo': 'No contesta'})

    assert resp.status_code == 200
    reserva.refresh_from_db()
    assert reserva.estado == 'PROGRAMADA' and reserva.movil_id is None
    assert ReservaEvento.objects.filter(reserva=reserva, tipo='CONDUCTOR_INCUMPLIO', movil=movil).exists()

    registro = central.get('/api/reservas/registro_conductores/').data
    assert registro[0]['patente'] == 'EST011' and registro[0]['no_llego'] == 1


@pytest.mark.django_db
def test_liberar_sin_incumplimiento_no_cuenta_en_el_registro(autenticar, crear_usuario, conductor, crear_reserva):
    _, movil = conductor('cond_l2', 'EST012', '23000000-3')
    reserva = _asignada(crear_reserva, movil, 180)
    central = autenticar(crear_usuario('cen_l2', rol_nombre='Central'))

    central.post(f'/api/reservas/{reserva.pk}/liberar/')

    assert ReservaEvento.objects.filter(reserva=reserva, tipo='LIBERADA_POR_CENTRAL').exists()
    assert central.get('/api/reservas/registro_conductores/').data == []


@pytest.mark.django_db
def test_liberar_solo_para_central(autenticar, conductor, crear_reserva):
    usuario, movil = conductor('cond_l3', 'EST013', '24000000-4')
    reserva = _asignada(crear_reserva, movil, 25)
    assert autenticar(usuario).post(f'/api/reservas/{reserva.pk}/liberar/').status_code == 403


@pytest.mark.django_db
def test_registro_cuenta_tambien_las_soltadas_tarde(autenticar, crear_usuario, conductor, crear_reserva):
    usuario, movil = conductor('cond_l4', 'EST014', '25000000-5')
    reserva = crear_reserva(90)
    cliente = autenticar(usuario)
    cliente.post(f'/api/reservas/{reserva.pk}/tomar/')
    cliente.post(f'/api/reservas/{reserva.pk}/soltar/')  # a 1 h 30: tarde

    registro = autenticar(crear_usuario('cen_l4', rol_nombre='Central')).get('/api/reservas/registro_conductores/').data

    assert registro[0]['patente'] == 'EST014' and registro[0]['soltadas_tarde'] == 1


@pytest.mark.django_db
def test_lista_de_pasajeros_con_incumplimientos(autenticar, crear_usuario):
    hoy = datetime.date.today()
    Pasajero.objects.create(rut='1-9', nombre='Sin', apellido='Falta', fecha_registro=hoy)
    uno = Pasajero.objects.create(rut='2-7', nombre='Uno', apellido='Falta', fecha_registro=hoy, incumplimientos=1)
    tres = Pasajero.objects.create(rut='3-5', nombre='Tres', apellido='Faltas', fecha_registro=hoy,
                                   incumplimientos=3, bloqueado_domicilio=1)

    resp = autenticar(crear_usuario('cen_ci1', rol_nombre='Central')).get('/api/pasajeros/con_incumplimientos/')

    assert resp.status_code == 200
    # solo los que tienen incumplimientos, con el bloqueado primero
    assert [p['rut'] for p in resp.data] == [tres.rut, uno.rut]
    assert resp.data[0]['bloqueado_domicilio'] == 1
