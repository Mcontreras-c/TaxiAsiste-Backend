"""
Integracion baja de conductores <-> reservas (las dos funciones se hicieron por
separado): dar de baja a un conductor no puede dejar reservas colgadas a su nombre.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from taxiasiste.solicitudes.models import Reserva, ReservaEvento


@pytest.fixture
def admin(crear_usuario):
    return crear_usuario('admin_bres', rol_nombre='Administrador')


@pytest.fixture
def conductor(crear_usuario, crear_socio, crear_movil):
    usuario = crear_usuario('cond_bres', rol_nombre='Conductor')
    socio = crear_socio('13131313-1', usuario=usuario)
    return socio, crear_movil(socio, 'BRES01')


def _reserva(minutos, movil, estado):
    return Reserva.objects.create(
        origen='Calle Test 1', fecha_hora_recogida=timezone.now() + timedelta(minutes=minutos),
        duracion_estimada_s=1200, distancia_estimada_m=6000, tarifa_estimada=2000,
        movil=movil, estado=estado,
    )


@pytest.mark.django_db
def test_la_baja_devuelve_las_reservas_asignadas_a_disponibles(autenticar, admin, conductor):
    socio, movil = conductor
    asignada = _reserva(180, movil, 'ASIGNADA')

    resp = autenticar(admin).post(f'/api/socios/{socio.pk}/dar_de_baja/')

    assert resp.status_code == 200, resp.data
    asignada.refresh_from_db()
    # Queda para que otro conductor la tome, sin movil a cargo
    assert asignada.estado == 'PROGRAMADA' and asignada.movil_id is None and asignada.fecha_tomada is None
    assert ReservaEvento.objects.filter(reserva=asignada, tipo='LIBERADA_POR_BAJA', movil=movil).exists()


@pytest.mark.django_db
def test_no_se_puede_dar_de_baja_con_una_reserva_en_camino(autenticar, admin, conductor):
    socio, movil = conductor
    en_camino = _reserva(30, movil, 'EN_CAMINO')

    resp = autenticar(admin).post(f'/api/socios/{socio.pk}/dar_de_baja/')

    assert resp.status_code == 409
    assert 'reserva' in resp.data['detail'].lower()
    socio.refresh_from_db(); en_camino.refresh_from_db()
    assert socio.estado_socio == 'ACTIVO' and en_camino.estado == 'EN_CAMINO'  # nada cambio


@pytest.mark.django_db
def test_dar_de_baja_la_cuenta_del_conductor_tambien_libera_sus_reservas(autenticar, admin, conductor):
    socio, movil = conductor
    asignada = _reserva(180, movil, 'ASIGNADA')

    resp = autenticar(admin).post(f'/api/usuarios/{socio.usuario_id}/dar_de_baja/')

    assert resp.status_code == 200, resp.data
    asignada.refresh_from_db()
    assert asignada.estado == 'PROGRAMADA' and asignada.movil_id is None


@pytest.mark.django_db
def test_las_reservas_ya_terminadas_no_se_tocan(autenticar, admin, conductor):
    socio, movil = conductor
    completada = _reserva(-300, movil, 'COMPLETADA')

    autenticar(admin).post(f'/api/socios/{socio.pk}/dar_de_baja/')

    completada.refresh_from_db()
    assert completada.estado == 'COMPLETADA' and completada.movil_id == movil.pk  # historial intacto


@pytest.mark.django_db
def test_un_conductor_dado_de_baja_no_puede_tomar_reservas(autenticar, admin, conductor, crear_usuario):
    socio, movil = conductor
    libre = Reserva.objects.create(
        origen='Calle Test 2', fecha_hora_recogida=timezone.now() + timedelta(hours=4),
        duracion_estimada_s=1200, distancia_estimada_m=6000, tarifa_estimada=2000,
    )
    autenticar(admin).post(f'/api/socios/{socio.pk}/dar_de_baja/')

    # Su cuenta ya no es valida: ni siquiera puede autenticarse
    from taxiasiste.usuarios.models import Usuario
    usuario = Usuario.objects.get(pk=socio.usuario_id)
    resp = autenticar(usuario).post(f'/api/reservas/{libre.pk}/tomar/')

    assert resp.status_code in (401, 403)
    libre.refresh_from_db()
    assert libre.estado == 'PROGRAMADA'
