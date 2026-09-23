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


@pytest.fixture
def conductor_con_movil(autenticar, crear_usuario, crear_socio, crear_movil):
    conductor = crear_usuario('condViaje', rol_nombre='Conductor')
    socio = crear_socio('77777777-7', usuario=conductor)
    movil = crear_movil(socio, 'PROP01')
    UbicacionActual.objects.create(movil=movil, lat=-33.45, lng=-70.66, actualizado_en=timezone.now())
    return conductor, movil


@pytest.mark.django_db
@pytest.mark.parametrize('estado', ['ASIGNADO', 'EN_CURSO'])
def test_conductor_con_viaje_activo_solo_ve_su_propio_movil(
    estado, autenticar, conductor_con_movil, movil_con_ubicacion,
):
    from taxiasiste.solicitudes.models import Solicitud

    conductor, movil = conductor_con_movil
    otro = movil_con_ubicacion('OTRO03', '88888888-8', hace_segundos=5)
    Solicitud.objects.create(origen='A', destino='B', movil=movil, estado=estado)

    resp = autenticar(conductor).get('/api/ubicaciones/')

    ids = [u['movil'] for u in resp.data]
    assert ids == [movil.id_movil]
    assert otro.id_movil not in ids


@pytest.mark.django_db
def test_conductor_sin_viaje_activo_ve_toda_la_flota(autenticar, conductor_con_movil, movil_con_ubicacion):
    conductor, movil = conductor_con_movil
    otro = movil_con_ubicacion('OTRO04', '99999999-9', hace_segundos=5)

    ids = [u['movil'] for u in autenticar(conductor).get('/api/ubicaciones/').data]

    assert movil.id_movil in ids and otro.id_movil in ids


@pytest.mark.django_db
def test_viaje_completado_no_restringe_al_conductor(autenticar, conductor_con_movil, movil_con_ubicacion):
    from taxiasiste.solicitudes.models import Solicitud

    conductor, movil = conductor_con_movil
    otro = movil_con_ubicacion('OTRO05', '10101010-1', hace_segundos=5)
    Solicitud.objects.create(origen='A', destino='B', movil=movil, estado='COMPLETADO')

    ids = [u['movil'] for u in autenticar(conductor).get('/api/ubicaciones/').data]

    assert otro.id_movil in ids


@pytest.mark.django_db
def test_central_sigue_viendo_toda_la_flota_aunque_haya_viajes(autenticar, crear_usuario, conductor_con_movil, movil_con_ubicacion):
    from taxiasiste.solicitudes.models import Solicitud

    _, movil = conductor_con_movil
    otro = movil_con_ubicacion('OTRO06', '12121212-1', hace_segundos=5)
    Solicitud.objects.create(origen='A', destino='B', movil=movil, estado='EN_CURSO')
    central = crear_usuario('centralViaje', rol_nombre='Central')

    ids = [u['movil'] for u in autenticar(central).get('/api/ubicaciones/').data]

    assert movil.id_movil in ids and otro.id_movil in ids


@pytest.mark.django_db
def test_conductor_ve_a_otros_solo_por_nombre_sin_patente_ni_rut(autenticar, conductor_con_movil, movil_con_ubicacion):
    conductor, movil = conductor_con_movil
    otro = movil_con_ubicacion('OTRO07', '13131313-1', hace_segundos=5)

    datos = {u['movil']: u for u in autenticar(conductor).get('/api/ubicaciones/').data}

    assert datos[otro.id_movil]['patente'] == ''
    assert datos[otro.id_movil]['socio_nombre'] == 'Juan Perez'
    assert '13131313' not in str(datos[otro.id_movil])
    # su propio movil se entrega completo
    assert datos[movil.id_movil]['patente'] == 'PROP01'


@pytest.mark.django_db
def test_central_recibe_patente_y_rut_completos(autenticar, crear_usuario, movil_con_ubicacion):
    otro = movil_con_ubicacion('OTRO08', '14141414-1', hace_segundos=5)
    central = crear_usuario('centralDatos', rol_nombre='Central')

    datos = {u['movil']: u for u in autenticar(central).get('/api/ubicaciones/').data}

    assert datos[otro.id_movil]['patente'] == 'OTRO08'
    assert '14141414-1' in datos[otro.id_movil]['socio_nombre']
