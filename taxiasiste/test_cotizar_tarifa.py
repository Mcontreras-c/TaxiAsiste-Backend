import pytest


class _Resp:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


def _geocode(lat, lng, formatted='Av. Falsa 123, Santiago'):
    return _Resp({'status': 'OK', 'results': [{
        'formatted_address': formatted,
        'geometry': {'location': {'lat': lat, 'lng': lng}},
        'address_components': [{'types': ['route']}],
    }]})


def _directions(*rutas):
    return _Resp({'status': 'OK', 'routes': [{
        'summary': nombre,
        'overview_polyline': {'points': ''},
        'legs': [{
            'distance': {'value': dist},
            'duration': {'value': dur},
            'start_location': {'lat': -33.42, 'lng': -70.73},
            'start_address': 'Hospital Félix Bulnes',
            'end_address': 'Destino',
        }],
    } for nombre, dist, dur in rutas]})


def _fake_get(capturadas, rutas):
    def fake(url, params=None, **kw):
        capturadas.append((url, params))
        if 'textsearch' in url:
            return _Resp({'status': 'REQUEST_DENIED', 'results': []})  # Places no habilitado -> cae a Geocoding
        return _geocode(-33.5, -70.7) if 'geocode' in url else _directions(*rutas)
    return fake


@pytest.mark.django_db
def test_cotiza_desde_hospital_con_alternativas(autenticar, crear_usuario, monkeypatch):
    llamadas = []
    monkeypatch.setattr('taxiasiste.views.requests.get',
                        _fake_get(llamadas, [('Ruta A', 3000, 600), ('Ruta B', 4000, 500)]))
    client = autenticar(crear_usuario('cotiza1', rol_nombre='Central'))

    resp = client.get('/api/cotizar_tarifa/', {'destino_texto': 'Av. Pajaritos 3000'})

    assert resp.status_code == 200
    assert len(resp.data['rutas']) == 2
    # 3000 m -> 15 tics, 600 s -> 10 tics: gana distancia. 500 + 15*200
    assert resp.data['rutas'][0]['tarifa_estimada'] == 3500
    # 4000 m -> 20 tics: 500 + 20*200
    assert resp.data['rutas'][1]['tarifa_estimada'] == 4500
    assert resp.data['origen']['direccion'] == 'Hospital Félix Bulnes, Cerro Navia'
    directions = [p for u, p in llamadas if 'directions' in u][0]
    assert directions['origin'] == 'Hospital Félix Bulnes, Cerro Navia'
    assert directions['alternatives'] == 'true'


@pytest.mark.django_db
def test_cotiza_desde_ubicacion_actual(autenticar, crear_usuario, monkeypatch):
    llamadas = []
    monkeypatch.setattr('taxiasiste.views.requests.get', _fake_get(llamadas, [('Ruta A', 1000, 120)]))
    client = autenticar(crear_usuario('cotiza2', rol_nombre='Conductor'))

    resp = client.get('/api/cotizar_tarifa/', {
        'origen_lat': -33.45, 'origen_lng': -70.66, 'destino_texto': 'Plaza de Armas',
    })

    assert resp.status_code == 200
    directions = [p for u, p in llamadas if 'directions' in u][0]
    assert directions['origin'] == '-33.45,-70.66'
    # 1000 m -> 5 tics: 500 + 1000
    assert resp.data['rutas'][0]['tarifa_estimada'] == 1500


@pytest.mark.django_db
def test_sin_destino_es_400(autenticar, crear_usuario):
    client = autenticar(crear_usuario('cotiza3', rol_nombre='Central'))
    assert client.get('/api/cotizar_tarifa/').status_code == 400


@pytest.mark.django_db
def test_requiere_autenticacion(client):
    assert client.get('/api/cotizar_tarifa/', {'destino_texto': 'x'}).status_code == 401


@pytest.mark.django_db
def test_nombre_de_lugar_se_busca_con_places(autenticar, crear_usuario, monkeypatch):
    """"Metro Pudahuel" debe resolverse como lugar (Places), no como la calle que devuelve Geocoding."""
    llamadas = []

    def fake(url, params=None, **kw):
        llamadas.append((url, params))
        if 'textsearch' in url:
            return _Resp({'status': 'OK', 'results': [{
                'name': 'Metro Pudahuel',
                'formatted_address': 'Av. San Pablo con Teniente Cruz, Pudahuel',
                'geometry': {'location': {'lat': -33.4467, 'lng': -70.7595}},
            }]})
        assert 'geocode' not in url  # con resultado de Places no se usa Geocoding
        return _directions(('Ruta A', 5000, 600))

    monkeypatch.setattr('taxiasiste.views.requests.get', fake)
    client = autenticar(crear_usuario('cotiza4', rol_nombre='Conductor'))

    resp = client.get('/api/cotizar_tarifa/', {'destino_texto': 'Metro Pudahuel'})

    assert resp.status_code == 200
    directions = [p for u, p in llamadas if 'directions' in u][0]
    assert directions['destination'] == '-33.4467,-70.7595'
    assert resp.data['destino']['direccion'] == 'Metro Pudahuel, Av. San Pablo con Teniente Cruz, Pudahuel'
