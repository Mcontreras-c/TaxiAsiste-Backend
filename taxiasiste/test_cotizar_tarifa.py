import pytest

from taxiasiste.views import calcular_rango_tarifa, calcular_tarifa_estimada


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
    """Cada ruta: (nombre, metros, segundos sin trafico[, segundos con trafico])."""
    def leg(ruta):
        _, dist, dur, *trafico = ruta
        datos = {
            'distance': {'value': dist},
            'duration': {'value': dur},
            'start_location': {'lat': -33.42, 'lng': -70.73},
            'start_address': 'Hospital Félix Bulnes',
            'end_address': 'Destino',
        }
        if trafico:
            datos['duration_in_traffic'] = {'value': trafico[0]}
        return datos

    return _Resp({'status': 'OK', 'routes': [{
        'summary': ruta[0],
        'overview_polyline': {'points': ''},
        'legs': [leg(ruta)],
    } for ruta in rutas]})


def _fake_get(capturadas, rutas, pesadas=None):
    """`pesadas`: rutas que devuelve Google con traffic_model=pessimistic (por defecto las mismas)."""
    def fake(url, params=None, **kw):
        capturadas.append((url, params))
        if 'directions' in url and (params or {}).get('traffic_model') == 'pessimistic':
            return _directions(*(rutas if pesadas is None else pesadas))
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


# ---------- rango de tarifa (minimo - maximo) ----------

@pytest.mark.django_db
def test_sin_trafico_el_rango_es_un_solo_valor(autenticar, crear_usuario, monkeypatch):
    monkeypatch.setattr('taxiasiste.views.requests.get', _fake_get([], [('Ruta A', 3000, 600)]))
    client = autenticar(crear_usuario('rango1', rol_nombre='Conductor'))

    ruta = client.get('/api/cotizar_tarifa/', {'destino_texto': 'Plaza'}).data['rutas'][0]

    assert ruta['tarifa_minima'] == ruta['tarifa_maxima'] == ruta['tarifa_estimada'] == 3500
    assert ruta['duracion_libre_s'] == 600


@pytest.mark.django_db
def test_con_trafico_el_maximo_suma_el_atraso_detenido(autenticar, crear_usuario, monkeypatch):
    # 5500 m: 27,5 tics. 9 min sin trafico, 11 min con trafico -> atraso de 2 min = 2 tics.
    monkeypatch.setattr('taxiasiste.views.requests.get', _fake_get([], [('Ruta A', 5500, 540, 660)]))
    client = autenticar(crear_usuario('rango2', rol_nombre='Conductor'))

    ruta = client.get('/api/cotizar_tarifa/', {'destino_texto': 'Plaza'}).data['rutas'][0]

    assert ruta['tarifa_minima'] == 6100  # 500 + 28 tics (distancia)
    assert ruta['tarifa_maxima'] == 6500  # 500 + ceil(27,5 + 2) = 30 tics
    assert ruta['tarifa_estimada'] == ruta['tarifa_minima']  # el campo de siempre no cambia
    assert ruta['duracion_s'] == 660 and ruta['duracion_libre_s'] == 540


@pytest.mark.django_db
def test_cada_ruta_alternativa_trae_su_propio_rango(autenticar, crear_usuario, monkeypatch):
    monkeypatch.setattr('taxiasiste.views.requests.get', _fake_get([], [
        ('Ruta A', 5500, 540, 660),
        ('Ruta B', 6000, 700, 700),
    ]))
    client = autenticar(crear_usuario('rango3', rol_nombre='Conductor'))

    a, b = client.get('/api/cotizar_tarifa/', {'destino_texto': 'Plaza'}).data['rutas']

    assert (a['tarifa_minima'], a['tarifa_maxima']) == (6100, 6500)
    assert (b['tarifa_minima'], b['tarifa_maxima']) == (6500, 6500)


def test_viaje_lento_el_minimo_ya_es_por_tiempo_y_el_maximo_lo_supera():
    # 2000 m (10 tics) en 25 min con trafico (5 min sin trafico): marca por tiempo.
    minima, maxima = calcular_rango_tarifa(2000, 1500, 300)
    assert minima == 500 + 25 * 200
    assert maxima == 500 + (10 + 20) * 200  # 10 tics de distancia + 20 min de atraso detenido


def test_el_atraso_no_cuenta_si_el_trafico_va_mas_rapido_que_el_tiempo_libre():
    # Google a veces da menos tiempo "con trafico" que el tiempo libre de referencia.
    assert calcular_rango_tarifa(5000, 500, 600) == (5500, 5500)  # 500 + 25 tics de distancia


@pytest.mark.parametrize('distancia_m', [0, 150, 300, 1999, 5500, 12000, 25600, 80000])
@pytest.mark.parametrize('libre_s', [0, 60, 300, 1800, 7200])
@pytest.mark.parametrize('extra_s', [-120, 0, 1, 59, 600, 3600])
def test_el_maximo_nunca_es_menor_que_el_minimo(distancia_m, libre_s, extra_s):
    con_trafico_s = max(0, libre_s + extra_s)

    minima, maxima = calcular_rango_tarifa(distancia_m, con_trafico_s, libre_s)

    assert minima <= maxima
    assert minima == calcular_tarifa_estimada(distancia_m, con_trafico_s)


# ---------- techo con trafico pesado ----------

@pytest.mark.django_db
def test_el_maximo_usa_el_trafico_pesado_de_google_si_es_peor(autenticar, crear_usuario, monkeypatch):
    # Ahora sin atraso (9 min libres y con trafico), pero Google estima 15 min con trafico pesado.
    llamadas = []
    monkeypatch.setattr('taxiasiste.views.requests.get', _fake_get(
        llamadas, [('Ruta A', 5500, 540, 540)], pesadas=[('Ruta A', 5500, 540, 900)],
    ))
    client = autenticar(crear_usuario('pesado1', rol_nombre='Conductor'))

    ruta = client.get('/api/cotizar_tarifa/', {'destino_texto': 'Plaza'}).data['rutas'][0]

    assert ruta['tarifa_minima'] == 6100  # el minimo no cambia: 500 + 28 tics de distancia
    assert ruta['tarifa_maxima'] == 7300  # 500 + ceil(27,5 + 6 min de atraso) = 34 tics
    assert ruta['duracion_trafico_pesado_s'] == 900
    directions = [p for u, p in llamadas if 'directions' in u]
    assert [p.get('traffic_model') for p in directions] == [None, 'pessimistic']  # la principal va primero


@pytest.mark.django_db
def test_si_el_trafico_de_ahora_ya_es_peor_que_el_pesado_manda_el_de_ahora(autenticar, crear_usuario, monkeypatch):
    monkeypatch.setattr('taxiasiste.views.requests.get', _fake_get(
        [], [('Ruta A', 5500, 540, 900)], pesadas=[('Ruta A', 5500, 540, 700)],
    ))
    client = autenticar(crear_usuario('pesado2', rol_nombre='Conductor'))

    ruta = client.get('/api/cotizar_tarifa/', {'destino_texto': 'Plaza'}).data['rutas'][0]

    assert ruta['tarifa_maxima'] == 7300  # atraso de ahora: 6 min


@pytest.mark.django_db
def test_si_la_ruta_no_aparece_en_la_consulta_pesada_se_ignora(autenticar, crear_usuario, monkeypatch):
    monkeypatch.setattr('taxiasiste.views.requests.get', _fake_get(
        [], [('Ruta A', 5500, 540, 660)], pesadas=[('Otra ruta', 5500, 540, 2000)],
    ))
    client = autenticar(crear_usuario('pesado3', rol_nombre='Conductor'))

    ruta = client.get('/api/cotizar_tarifa/', {'destino_texto': 'Plaza'}).data['rutas'][0]

    assert ruta['tarifa_maxima'] == 6500  # solo el atraso de ahora (2 min)
    assert ruta['duracion_trafico_pesado_s'] is None


@pytest.mark.django_db
@pytest.mark.parametrize('falla', ['denegado', 'sin_red', 'json_roto'])
def test_si_falla_la_consulta_de_trafico_pesado_el_cotizador_sigue_funcionando(
    falla, autenticar, crear_usuario, monkeypatch,
):
    import requests

    normal = _fake_get([], [('Ruta A', 5500, 540, 660)])

    def fake(url, params=None, **kw):
        if 'directions' in url and (params or {}).get('traffic_model') == 'pessimistic':
            if falla == 'sin_red':
                raise requests.ConnectionError('sin red')
            if falla == 'json_roto':
                class Rota(_Resp):
                    def json(self):
                        raise ValueError('no es json')
                return Rota({})
            return _Resp({'status': 'REQUEST_DENIED', 'routes': []})
        return normal(url, params, **kw)

    monkeypatch.setattr('taxiasiste.views.requests.get', fake)
    client = autenticar(crear_usuario(f'pesado4_{falla}', rol_nombre='Conductor'))

    resp = client.get('/api/cotizar_tarifa/', {'destino_texto': 'Plaza'})

    assert resp.status_code == 200
    ruta = resp.data['rutas'][0]
    assert (ruta['tarifa_minima'], ruta['tarifa_maxima']) == (6100, 6500)


def test_rango_con_duracion_pesada():
    assert calcular_rango_tarifa(5500, 540, 540, 900) == (6100, 7300)
    assert calcular_rango_tarifa(5500, 540, 540, None) == (6100, 6100)
