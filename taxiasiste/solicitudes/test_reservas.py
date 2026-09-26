from datetime import timedelta

import pytest
from django.utils import timezone

from taxiasiste.solicitudes import reservas_logic
from taxiasiste.solicitudes.models import Reserva, ReservaEvento

DURACION = 1200  # 20 min de viaje


# ------------------------------------------------------------ regla del margen

def _t(minutos):
    base = timezone.now().replace(microsecond=0)
    return base + timedelta(minutes=minutos)


def test_franja_incluye_ida_viaje_y_margen():
    recogida = _t(180)
    inicio, fin = reservas_logic.franja(recogida, DURACION)
    # 20 min de ida + 15 de margen antes; 20 de viaje + 15 de margen despues
    assert inicio == recogida - timedelta(minutes=35)
    assert fin == recogida + timedelta(minutes=35)
    assert reservas_logic.hora_maxima_salida(recogida, DURACION) == inicio


def test_reservas_muy_separadas_no_se_cruzan():
    assert not reservas_logic.se_cruzan((_t(180), DURACION), (_t(400), DURACION))


def test_reservas_a_la_misma_hora_se_cruzan():
    assert reservas_logic.se_cruzan((_t(180), DURACION), (_t(180), DURACION))


def test_justo_en_el_limite_del_margen_se_permite():
    # la franja de A termina exactamente cuando empieza la de B (70 min entre recogidas)
    assert not reservas_logic.se_cruzan((_t(180), DURACION), (_t(250), DURACION))


def test_un_minuto_dentro_del_margen_se_cruzan():
    assert reservas_logic.se_cruzan((_t(180), DURACION), (_t(249), DURACION))


def test_el_cruce_depende_de_la_duracion_del_viaje():
    # Con viajes de 5 min basta con 40 min entre recogidas; con 40 min de viaje no.
    assert not reservas_logic.se_cruzan((_t(180), 300), (_t(225), 300))
    assert reservas_logic.se_cruzan((_t(180), 2400), (_t(225), 2400))


# ------------------------------------------------------------------- utilidades

class _Resp:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


def _google_ok(distancia_m=6000, duracion_s=DURACION):
    def fake(url, params=None, **kw):
        if 'directions' in url:
            return _Resp({'status': 'OK', 'routes': [{'legs': [{
                'distance': {'value': distancia_m},
                'duration': {'value': duracion_s},
                'start_location': {'lat': -33.4, 'lng': -70.7},
                'start_address': 'x', 'end_address': 'y',
            }]}]})
        if 'textsearch' in url:
            return _Resp({'status': 'ZERO_RESULTS', 'results': []})
        return _Resp({'status': 'OK', 'results': [{
            'formatted_address': 'Av. Falsa 123, Santiago',
            'geometry': {'location': {'lat': -33.45, 'lng': -70.66}},
            'address_components': [{'types': ['route']}],
        }]})
    return fake


@pytest.fixture
def conductor(crear_usuario, crear_socio, crear_movil):
    """Un conductor completo: usuario + socio activo + movil. Devuelve (usuario, movil)."""
    def _crear(nombre, patente, rut):
        usuario = crear_usuario(nombre, rol_nombre='Conductor')
        socio = crear_socio(rut, nombre=nombre.capitalize(), usuario=usuario)
        return usuario, crear_movil(socio, patente)
    return _crear


@pytest.fixture
def crear_reserva(db):
    def _crear(minutos, duracion_s=DURACION, **extra):
        return Reserva.objects.create(
            origen='Calle Test 1', fecha_hora_recogida=_t(minutos),
            duracion_estimada_s=duracion_s, distancia_estimada_m=6000, tarifa_estimada=2000,
            **extra,
        )
    return _crear


# ------------------------------------------------------------ crear (Central)

@pytest.mark.django_db
def test_central_crea_reserva(autenticar, crear_usuario, monkeypatch):
    monkeypatch.setattr('taxiasiste.views.requests.get', _google_ok())
    central = crear_usuario('cen_res1', rol_nombre='Central')

    resp = autenticar(central).post('/api/reservas/', {
        'origen': 'Av. Falsa 123', 'fecha_hora_recogida': _t(180).isoformat(), 'observaciones': 'Silla de ruedas',
    })

    assert resp.status_code == 201, resp.data
    assert resp.data['folio'].startswith('RES-')
    assert resp.data['estado'] == 'PROGRAMADA'
    assert resp.data['destino'] == 'Hospital Félix Bulnes, Cerro Navia'
    assert resp.data['duracion_estimada_s'] == DURACION
    # 6000 m -> 30 tics, 1200 s -> 20 tics: gana la distancia. 500 + 30*200
    assert resp.data['tarifa_estimada'] == 6500
    assert resp.data['salida_base_maxima'] is not None
    assert ReservaEvento.objects.filter(reserva_id=resp.data['id_reserva'], tipo='CREADA').exists()


@pytest.mark.django_db
def test_no_se_puede_reservar_con_menos_de_30_minutos(autenticar, crear_usuario, monkeypatch):
    monkeypatch.setattr('taxiasiste.views.requests.get', _google_ok())
    resp = autenticar(crear_usuario('cen_res2', rol_nombre='Central')).post(
        '/api/reservas/', {'origen': 'Av. Falsa 123', 'fecha_hora_recogida': _t(10).isoformat()})
    assert resp.status_code == 400
    assert '30 minutos' in resp.data['detail']


@pytest.mark.django_db
def test_no_se_puede_reservar_a_mas_de_24_horas(autenticar, crear_usuario, monkeypatch):
    monkeypatch.setattr('taxiasiste.views.requests.get', _google_ok())
    resp = autenticar(crear_usuario('cen_res3', rol_nombre='Central')).post(
        '/api/reservas/', {'origen': 'Av. Falsa 123', 'fecha_hora_recogida': _t(25 * 60).isoformat()})
    assert resp.status_code == 400
    assert '24 horas' in resp.data['detail']


@pytest.mark.django_db
def test_conductor_no_puede_crear_reservas(autenticar, conductor):
    usuario, _ = conductor('cond_crea', 'RSV001', '11111111-1')
    resp = autenticar(usuario).post('/api/reservas/', {'origen': 'X', 'fecha_hora_recogida': _t(180).isoformat()})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_tesorero_no_ve_reservas(autenticar, crear_usuario):
    assert autenticar(crear_usuario('tes_res', rol_nombre='Tesorero')).get('/api/reservas/').status_code == 403


@pytest.mark.django_db
def test_central_lista_solo_vigentes_por_defecto(autenticar, crear_usuario, crear_reserva):
    vigente = crear_reserva(180)
    crear_reserva(200, estado='CANCELADA')
    resp = autenticar(crear_usuario('cen_res4', rol_nombre='Central')).get('/api/reservas/')
    assert [r['folio'] for r in resp.data] == [vigente.folio]


@pytest.mark.django_db
def test_central_cancela_reserva(autenticar, crear_usuario, crear_reserva):
    reserva = crear_reserva(180)
    resp = autenticar(crear_usuario('cen_res5', rol_nombre='Central')).post(f'/api/reservas/{reserva.pk}/cancelar/')
    assert resp.status_code == 200
    reserva.refresh_from_db()
    assert reserva.estado == 'CANCELADA'
    assert ReservaEvento.objects.filter(reserva=reserva, tipo='CANCELADA').exists()


# ------------------------------------------------------ disponibles y tomar

@pytest.mark.django_db
def test_disponibles_oculta_al_pasajero(autenticar, conductor, crear_reserva):
    from taxiasiste.solicitudes.models import Pasajero
    import datetime
    pasajero = Pasajero.objects.create(rut='9999999-9', nombre='Ana', apellido='Lopez', fecha_registro=datetime.date.today())
    crear_reserva(180, pasajero=pasajero)
    usuario, _ = conductor('cond_disp', 'RSV002', '22222222-2')

    resp = autenticar(usuario).get('/api/reservas/disponibles/')

    assert resp.status_code == 200 and len(resp.data) == 1
    assert resp.data[0]['pasajero_nombre'] is None
    assert resp.data[0]['puede_tomar'] is True


@pytest.mark.django_db
def test_disponibles_no_muestra_las_que_ya_no_alcanza(autenticar, conductor, crear_reserva):
    crear_reserva(20)  # hora maxima de salida = hace 15 min
    usuario, _ = conductor('cond_disp2', 'RSV003', '33333333-3')
    assert autenticar(usuario).get('/api/reservas/disponibles/').data == []


@pytest.mark.django_db
def test_tomar_reserva(autenticar, conductor, crear_reserva):
    reserva = crear_reserva(180)
    usuario, movil = conductor('cond_toma', 'RSV004', '44444444-4')

    resp = autenticar(usuario).post(f'/api/reservas/{reserva.pk}/tomar/')

    assert resp.status_code == 200, resp.data
    reserva.refresh_from_db()
    assert reserva.estado == 'ASIGNADA' and reserva.movil_id == movil.pk
    assert ReservaEvento.objects.filter(reserva=reserva, tipo='TOMADA', movil=movil).exists()


@pytest.mark.django_db
def test_mias_muestra_los_datos_del_pasajero(autenticar, conductor, crear_reserva):
    from taxiasiste.solicitudes.models import Pasajero
    import datetime
    pasajero = Pasajero.objects.create(rut='8888888-8', nombre='Luis', apellido='Soto', telefono='+56911111111',
                                       fecha_registro=datetime.date.today())
    reserva = crear_reserva(180, pasajero=pasajero)
    usuario, _ = conductor('cond_mias', 'RSV005', '55555555-5')
    cliente = autenticar(usuario)
    cliente.post(f'/api/reservas/{reserva.pk}/tomar/')

    resp = cliente.get('/api/reservas/mias/')

    assert len(resp.data) == 1
    assert resp.data[0]['pasajero_nombre'] == 'Luis Soto'
    assert resp.data[0]['pasajero_telefono'] == '+56911111111'


@pytest.mark.django_db
def test_no_puede_tomar_dos_reservas_que_se_cruzan(autenticar, conductor, crear_reserva):
    a, b = crear_reserva(180), crear_reserva(240)  # 60 min entre recogidas < 70 necesarios
    usuario, _ = conductor('cond_cruce', 'RSV006', '66666666-6')
    cliente = autenticar(usuario)

    assert cliente.post(f'/api/reservas/{a.pk}/tomar/').status_code == 200
    resp = cliente.post(f'/api/reservas/{b.pk}/tomar/')

    assert resp.status_code == 409
    assert 'se cruza' in resp.data['detail'].lower()
    assert a.folio in resp.data['detail']
    b.refresh_from_db()
    assert b.estado == 'PROGRAMADA'


@pytest.mark.django_db
def test_disponibles_marca_la_que_se_cruza_con_el_motivo(autenticar, conductor, crear_reserva):
    a, b = crear_reserva(180), crear_reserva(240)
    usuario, _ = conductor('cond_motivo', 'RSV007', '77777777-7')
    cliente = autenticar(usuario)
    cliente.post(f'/api/reservas/{a.pk}/tomar/')

    fila = {r['folio']: r for r in cliente.get('/api/reservas/disponibles/').data}

    assert fila[b.folio]['puede_tomar'] is False
    assert a.folio in fila[b.folio]['motivo_bloqueo']


@pytest.mark.django_db
def test_puede_tomar_dos_reservas_con_el_margen_justo(autenticar, conductor, crear_reserva):
    a, b = crear_reserva(180), crear_reserva(250)  # 70 min: justo lo necesario
    usuario, _ = conductor('cond_justo', 'RSV008', '88888888-8')
    cliente = autenticar(usuario)
    assert cliente.post(f'/api/reservas/{a.pk}/tomar/').status_code == 200
    assert cliente.post(f'/api/reservas/{b.pk}/tomar/').status_code == 200


@pytest.mark.django_db
def test_maximo_tres_reservas_activas(autenticar, conductor, crear_reserva):
    reservas = [crear_reserva(180 + i * 120) for i in range(4)]  # bien separadas
    usuario, _ = conductor('cond_tope', 'RSV009', '99999999-9')
    cliente = autenticar(usuario)
    for r in reservas[:3]:
        assert cliente.post(f'/api/reservas/{r.pk}/tomar/').status_code == 200

    resp = cliente.post(f'/api/reservas/{reservas[3].pk}/tomar/')

    assert resp.status_code == 409
    assert '3 reservas' in resp.data['detail']


@pytest.mark.django_db
def test_solo_un_conductor_se_lleva_la_reserva(autenticar, conductor, crear_reserva):
    reserva = crear_reserva(180)
    u1, _ = conductor('cond_a', 'RSV010', '10101010-1')
    u2, _ = conductor('cond_b', 'RSV011', '20202020-2')

    assert autenticar(u1).post(f'/api/reservas/{reserva.pk}/tomar/').status_code == 200
    resp = autenticar(u2).post(f'/api/reservas/{reserva.pk}/tomar/')

    assert resp.status_code == 409
    reserva.refresh_from_db()
    assert reserva.movil.patente == 'RSV010'


@pytest.mark.django_db
def test_no_se_puede_tomar_pasada_la_hora_maxima_de_salida(autenticar, conductor, crear_reserva):
    reserva = crear_reserva(20)  # ya no alcanza
    usuario, _ = conductor('cond_tarde', 'RSV012', '30303030-3')
    resp = autenticar(usuario).post(f'/api/reservas/{reserva.pk}/tomar/')
    assert resp.status_code == 409
    assert 'hora máxima de salida' in resp.data['detail']


@pytest.mark.django_db
def test_conductor_bloqueado_no_puede_tomar(autenticar, conductor, crear_reserva):
    reserva = crear_reserva(180)
    usuario, movil = conductor('cond_bloq', 'RSV013', '40404040-4')
    movil.estado_operativo = 'BLOQUEADO'
    movil.save(update_fields=['estado_operativo'])
    assert autenticar(usuario).post(f'/api/reservas/{reserva.pk}/tomar/').status_code == 403


# --------------------------------------------------------------------- soltar

@pytest.mark.django_db
def test_soltar_con_anticipacion_no_tiene_consecuencia(autenticar, conductor, crear_reserva):
    reserva = crear_reserva(300)  # 5 h antes
    usuario, movil = conductor('cond_suelta', 'RSV014', '50505050-5')
    cliente = autenticar(usuario)
    cliente.post(f'/api/reservas/{reserva.pk}/tomar/')

    resp = cliente.post(f'/api/reservas/{reserva.pk}/soltar/')

    assert resp.status_code == 200
    assert resp.data['soltada_tarde'] is False
    reserva.refresh_from_db()
    assert reserva.estado == 'PROGRAMADA' and reserva.movil_id is None
    assert ReservaEvento.objects.filter(reserva=reserva, tipo='SOLTADA', movil=movil).exists()


@pytest.mark.django_db
def test_soltar_a_menos_de_2_horas_queda_registrado_como_tarde(autenticar, conductor, crear_reserva):
    reserva = crear_reserva(90)  # a 1 h 30 de la recogida (aun alcanza a tomarla)
    usuario, movil = conductor('cond_suelta2', 'RSV015', '60606060-6')
    cliente = autenticar(usuario)
    cliente.post(f'/api/reservas/{reserva.pk}/tomar/')

    resp = cliente.post(f'/api/reservas/{reserva.pk}/soltar/')

    assert resp.data['soltada_tarde'] is True
    assert ReservaEvento.objects.filter(reserva=reserva, tipo='SOLTADA_TARDE', movil=movil).exists()


@pytest.mark.django_db
def test_no_puede_soltar_una_reserva_ajena(autenticar, conductor, crear_reserva):
    reserva = crear_reserva(180)
    u1, _ = conductor('cond_due', 'RSV016', '70707070-7')
    u2, _ = conductor('cond_otro', 'RSV017', '80808080-8')
    autenticar(u1).post(f'/api/reservas/{reserva.pk}/tomar/')

    resp = autenticar(u2).post(f'/api/reservas/{reserva.pk}/soltar/')

    assert resp.status_code == 403
    reserva.refresh_from_db()
    assert reserva.estado == 'ASIGNADA'


@pytest.mark.django_db
def test_las_horas_salen_con_zona_horaria(autenticar, conductor, crear_reserva):
    """Sin la 'Z' el navegador leeria la hora como local y se correria 3 h."""
    crear_reserva(180)
    usuario, _ = conductor('cond_zona', 'RSV018', '12121212-1')
    item = autenticar(usuario).get('/api/reservas/disponibles/').json()[0]
    for campo in ('fecha_hora_recogida', 'salida_base_maxima', 'libre_desde'):
        assert item[campo].endswith('Z'), f'{campo} sin zona: {item[campo]}'
