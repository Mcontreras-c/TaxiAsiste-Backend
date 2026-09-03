from datetime import timedelta

import pytest
from django.utils import timezone
from taxiasiste.moviles.models import UbicacionActual


@pytest.fixture
def movil_con_ubicacion(crear_socio, crear_movil):
    def _crear(patente, rut, hace_segundos):
        movil = crear_movil(crear_socio(rut), patente)
        UbicacionActual.objects.create(
            movil=movil,
            lat=-33.45,
            lng=-70.66,
            actualizado_en=timezone.now() - timedelta(seconds=hace_segundos),
        )
        return movil

    return _crear


@pytest.mark.django_db
def test_solo_lista_moviles_reportados_en_los_ultimos_45s(autenticar, crear_usuario, movil_con_ubicacion):
    """Ver SEGUNDOS_ONLINE en moviles/views.py — un movil sin GPS reciente
    desaparece del mapa aunque su ultima posicion conocida siga en la tabla."""
    reciente = movil_con_ubicacion('RECI01', '44444444-4', hace_segundos=10)
    viejo = movil_con_ubicacion('VIEJ02', '55555555-5', hace_segundos=90)
    central = crear_usuario('centralX', rol_nombre='Central')
    client = autenticar(central)

    resp = client.get('/api/ubicaciones/')

    ids = [u['movil'] for u in resp.data]
    assert reciente.id_movil in ids
    assert viejo.id_movil not in ids


@pytest.mark.django_db
def test_mia_requiere_movil_vinculado_al_usuario(autenticar, crear_usuario):
    conductor = crear_usuario('conductorSinMovil', rol_nombre='Conductor')
    client = autenticar(conductor)

    resp = client.post('/api/ubicaciones/mia/', {'lat': -33.45, 'lng': -70.66})

    assert resp.status_code == 404


@pytest.mark.django_db
def test_mia_redondea_coordenadas_con_mas_de_6_decimales(autenticar, crear_usuario, crear_socio, crear_movil):
    """RoundingDecimalField (serializers.py): el GPS de un telefono real da
    7+ decimales, que Oracle (NUMBER(10,6)) rechazaria sin este redondeo."""
    conductor = crear_usuario('conductorConMovil', rol_nombre='Conductor')
    socio = crear_socio('66666666-6', usuario=conductor)
    crear_movil(socio, 'CCCC33')
    client = autenticar(conductor)

    resp = client.post('/api/ubicaciones/mia/', {'lat': -33.4489123456, 'lng': -70.6693987654})

    assert resp.status_code == 200
    assert str(resp.data['lat']) == '-33.448912'
    assert str(resp.data['lng']) == '-70.669399'
