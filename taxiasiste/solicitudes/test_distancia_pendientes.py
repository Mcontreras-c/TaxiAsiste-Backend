import pytest

from taxiasiste.solicitudes.models import Solicitud


class _FakeResponse:
    def __init__(self, json_data):
        self._json_data = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def _geocoding_ok(lat, lng, formatted='Av. Falsa 123, Santiago, Chile'):
    return _FakeResponse({
        'status': 'OK',
        'results': [{
            'formatted_address': formatted,
            'geometry': {'location': {'lat': lat, 'lng': lng}},
            'address_components': [{'types': ['route']}],
        }],
    })


def _geocoding_sin_calle():
    """Un resultado generico (comuna/region), sin componente 'route'."""
    return _FakeResponse({
        'status': 'OK',
        'results': [{
            'formatted_address': 'Cerro Navia, Chile',
            'geometry': {'location': {'lat': -33.4, 'lng': -70.7}},
            'address_components': [{'types': ['administrative_area_level_3']}],
        }],
    })


def _directions_ok(distancia_m, duracion_s):
    return _FakeResponse({
        'status': 'OK',
        'routes': [{
            'overview_polyline': {'points': ''},
            'legs': [{'distance': {'value': distancia_m}, 'duration': {'value': duracion_s}}],
        }],
    })


@pytest.mark.django_db
def test_crear_solicitud_geocodifica_el_origen(autenticar, crear_usuario, monkeypatch):
    """perform_create llama a Google Geocoding con el origen y guarda
    origen_lat/origen_lng -- sin esto, pendientes_con_distancia no puede
    calcularle distancia/ETA a ninguna solicitud nueva."""
    monkeypatch.setattr(
        'taxiasiste.views.requests.get',
        lambda *a, **k: _geocoding_ok(-33.44, -70.65),
    )
    central = crear_usuario('centralGeo1', rol_nombre='Central')
    client = autenticar(central)

    resp = client.post('/api/solicitudes/', {'origen': 'Plaza de Armas 1'})

    assert resp.status_code == 201
    solicitud = Solicitud.objects.get(id_solicitud=resp.data['id_solicitud'])
    assert float(solicitud.origen_lat) == pytest.approx(-33.44)
    assert float(solicitud.origen_lng) == pytest.approx(-70.65)


@pytest.mark.django_db
def test_crear_solicitud_no_falla_si_geocoding_falla(autenticar, crear_usuario, monkeypatch):
    """Best-effort: si Google no encuentra la calle, la solicitud igual se
    crea (solo queda sin origen_lat/lng, y por lo tanto sin distancia/ETA)."""
    monkeypatch.setattr('taxiasiste.views.requests.get', lambda *a, **k: _geocoding_sin_calle())
    central = crear_usuario('centralGeo2', rol_nombre='Central')
    client = autenticar(central)

    resp = client.post('/api/solicitudes/', {'origen': 'una direccion rara'})

    assert resp.status_code == 201
    solicitud = Solicitud.objects.get(id_solicitud=resp.data['id_solicitud'])
    assert solicitud.origen_lat is None
    assert solicitud.origen_lng is None


@pytest.mark.django_db
def test_pendientes_con_distancia_requiere_lat_lng(autenticar, crear_usuario):
    conductor = crear_usuario('conductorDist1', rol_nombre='Conductor')
    client = autenticar(conductor)

    resp = client.get('/api/solicitudes/pendientes_con_distancia/')

    assert resp.status_code == 400


@pytest.mark.django_db
def test_pendientes_con_distancia_ordena_mayor_espera_primero(autenticar, crear_usuario):
    """A diferencia de /pendientes/ (mas nueva primero), esta lista va de
    mas vieja a mas nueva -- el diseño de Mobile pide "mayor espera primero"
    para priorizar al pasajero que lleva mas tiempo esperando."""
    conductor = crear_usuario('conductorDist2', rol_nombre='Conductor')
    vieja = Solicitud.objects.create(origen='Direccion A', destino='Aeropuerto')
    nueva = Solicitud.objects.create(origen='Direccion B', destino='Aeropuerto')
    Solicitud.objects.filter(pk=vieja.pk).update(fecha_hora='2026-01-01T10:00:00Z')
    Solicitud.objects.filter(pk=nueva.pk).update(fecha_hora='2026-01-01T10:05:00Z')
    client = autenticar(conductor)

    resp = client.get('/api/solicitudes/pendientes_con_distancia/', {'lat': -33.45, 'lng': -70.66})

    assert resp.status_code == 200
    ids = [item['id_solicitud'] for item in resp.data]
    assert ids == [vieja.id_solicitud, nueva.id_solicitud]


@pytest.mark.django_db
def test_pendientes_con_distancia_calcula_distancia_y_duracion(autenticar, crear_usuario, monkeypatch):
    monkeypatch.setattr(
        'taxiasiste.views.requests.get',
        lambda *a, **k: _directions_ok(distancia_m=1800, duracion_s=360),
    )
    conductor = crear_usuario('conductorDist3', rol_nombre='Conductor')
    solicitud = Solicitud.objects.create(origen='Direccion con coords', destino='Aeropuerto')
    Solicitud.objects.filter(pk=solicitud.pk).update(origen_lat=-33.44, origen_lng=-70.65)
    client = autenticar(conductor)

    resp = client.get('/api/solicitudes/pendientes_con_distancia/', {'lat': -33.45, 'lng': -70.66})

    assert resp.status_code == 200
    item = resp.data[0]
    assert item['distancia_km'] == 1.8
    assert item['duracion_min'] == 6


@pytest.mark.django_db
def test_pendientes_con_distancia_sin_coords_devuelve_null(autenticar, crear_usuario):
    """Una solicitud cuyo origen nunca se pudo geocodificar (origen_lat null)
    no debe romper el endpoint -- simplemente queda sin distancia/ETA."""
    conductor = crear_usuario('conductorDist4', rol_nombre='Conductor')
    Solicitud.objects.create(origen='Direccion sin geocodificar', destino='Aeropuerto')
    client = autenticar(conductor)

    resp = client.get('/api/solicitudes/pendientes_con_distancia/', {'lat': -33.45, 'lng': -70.66})

    assert resp.status_code == 200
    assert resp.data[0]['distancia_km'] is None
    assert resp.data[0]['duracion_min'] is None
