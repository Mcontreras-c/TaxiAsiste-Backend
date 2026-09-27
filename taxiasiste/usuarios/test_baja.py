import datetime

import pytest
from django.utils import timezone

from taxiasiste.moviles.models import FilaBase, Movil, UbicacionActual
from taxiasiste.socios.models import Bloqueo, Socio
from taxiasiste.solicitudes.models import Solicitud
from taxiasiste.usuarios.bajas import BajaError, dar_de_baja_usuario
from taxiasiste.usuarios.models import Usuario


@pytest.fixture
def admin(crear_usuario):
    return crear_usuario('admin_baja', rol_nombre='Administrador')


@pytest.fixture
def conductor_completo(crear_usuario, crear_socio, crear_movil):
    """Conductor con cuenta, socio, movil, entrada en la fila y ubicacion."""
    usuario = crear_usuario('cond_baja', rol_nombre='Conductor')
    socio = crear_socio('12345678-5', usuario=usuario)
    movil = crear_movil(socio, 'BAJA01')
    FilaBase.objects.create(movil=movil, posicion=1, fecha_ingreso=timezone.now(), estado='EN_ESPERA')
    UbicacionActual.objects.create(movil=movil, lat=-33.45, lng=-70.66, actualizado_en=timezone.now())
    return usuario, socio, movil


# ---------- autenticacion ----------

@pytest.mark.django_db
def test_token_de_un_usuario_inactivo_deja_de_servir(autenticar, crear_usuario):
    """Vaciar sesion_actual no basta (un valor vacio omite la comparacion del sid):
    la autenticacion rechaza por estado."""
    usuario = crear_usuario('token_baja', rol_nombre='Central')
    client = autenticar(usuario)
    assert client.get('/api/usuarios/me/').status_code == 200

    usuario.estado = 'INACTIVO'
    usuario.sesion_actual = None
    usuario.save(update_fields=['estado', 'sesion_actual'])

    assert client.get('/api/usuarios/me/').status_code == 401


# ---------- permisos ----------

@pytest.mark.django_db
@pytest.mark.parametrize('accion', ['dar_de_baja', 'reactivar'])
def test_solo_administrador_puede_dar_de_baja_o_reactivar(accion, autenticar, crear_usuario):
    central = crear_usuario('central_baja', rol_nombre='Central')
    objetivo = crear_usuario('objetivo_baja', rol_nombre='Tesorero')

    resp = autenticar(central).post(f'/api/usuarios/{int(objetivo.id_usuario)}/{accion}/')

    assert resp.status_code == 403


# ---------- baja de usuario (personal del sindicato) ----------

@pytest.mark.django_db
def test_baja_de_usuario_lo_deja_inactivo_sin_borrarlo(autenticar, admin, crear_usuario):
    objetivo = crear_usuario('personal_baja', rol_nombre='Central')
    objetivo.sesion_actual = 'sesion-vieja'
    objetivo.save(update_fields=['sesion_actual'])

    resp = autenticar(admin).post(f'/api/usuarios/{int(objetivo.id_usuario)}/dar_de_baja/')

    assert resp.status_code == 200
    objetivo.refresh_from_db()
    assert objetivo.estado == 'INACTIVO'
    assert not objetivo.sesion_actual
    assert Usuario.objects.filter(pk=objetivo.pk).exists()


@pytest.mark.django_db
def test_usuario_dado_de_baja_no_puede_iniciar_sesion(autenticar, admin, crear_usuario, api_client):
    objetivo = crear_usuario('login_baja', password='Clave2026!', rol_nombre='Central')
    autenticar(admin).post(f'/api/usuarios/{int(objetivo.id_usuario)}/dar_de_baja/')

    resp = api_client.post('/api/login/', {'username': 'login_baja', 'password': 'Clave2026!'}, format='json')

    assert resp.status_code == 403


@pytest.mark.django_db
def test_no_puede_darse_de_baja_a_si_mismo(autenticar, admin):
    resp = autenticar(admin).post(f'/api/usuarios/{int(admin.id_usuario)}/dar_de_baja/')

    assert resp.status_code == 409
    assert 'ti mismo' in resp.data['detail']
    admin.refresh_from_db()
    assert admin.estado == 'ACTIVO'


@pytest.mark.django_db
def test_no_se_puede_dar_de_baja_al_ultimo_administrador(admin, crear_usuario):
    """La vista siempre tiene un administrador activo (quien la usa), asi que la
    regla se prueba sobre el servicio, tambien pensado para uso desde comandos."""
    otro = crear_usuario('no_admin_baja', rol_nombre='Central')

    with pytest.raises(BajaError) as error:
        dar_de_baja_usuario(admin, solicitante=otro)

    assert 'último administrador' in error.value.detail
    admin.refresh_from_db()
    assert admin.estado == 'ACTIVO'


@pytest.mark.django_db
def test_se_puede_dar_de_baja_a_un_administrador_si_queda_otro(autenticar, admin, crear_usuario):
    otro_admin = crear_usuario('admin2_baja', rol_nombre='Administrador')

    resp = autenticar(admin).post(f'/api/usuarios/{int(otro_admin.id_usuario)}/dar_de_baja/')

    assert resp.status_code == 200


@pytest.mark.django_db
def test_dar_de_baja_a_uno_ya_inactivo_es_409(autenticar, admin, crear_usuario):
    objetivo = crear_usuario('doble_baja', rol_nombre='Central', estado='INACTIVO')

    resp = autenticar(admin).post(f'/api/usuarios/{int(objetivo.id_usuario)}/dar_de_baja/')

    assert resp.status_code == 409


@pytest.mark.django_db
def test_reactivar_usuario(autenticar, admin, crear_usuario):
    objetivo = crear_usuario('reactivar_uno', rol_nombre='Central', estado='INACTIVO')

    resp = autenticar(admin).post(f'/api/usuarios/{int(objetivo.id_usuario)}/reactivar/')

    assert resp.status_code == 200
    objetivo.refresh_from_db()
    assert objetivo.estado == 'ACTIVO'


@pytest.mark.django_db
def test_reactivar_a_uno_activo_es_409(autenticar, admin, crear_usuario):
    objetivo = crear_usuario('ya_activo', rol_nombre='Central')

    resp = autenticar(admin).post(f'/api/usuarios/{int(objetivo.id_usuario)}/reactivar/')

    assert resp.status_code == 409


@pytest.mark.django_db
def test_delete_de_usuarios_esta_deshabilitado(autenticar, admin, crear_usuario):
    objetivo = crear_usuario('no_borrar', rol_nombre='Central')

    resp = autenticar(admin).delete(f'/api/usuarios/{int(objetivo.id_usuario)}/')

    assert resp.status_code == 405
    assert Usuario.objects.filter(pk=objetivo.pk).exists()


# ---------- baja de un conductor (usuario con socio) ----------

@pytest.mark.django_db
def test_baja_de_la_cuenta_de_un_conductor_da_de_baja_al_socio_completo(autenticar, admin, conductor_completo):
    usuario, socio, movil = conductor_completo

    resp = autenticar(admin).post(f'/api/usuarios/{int(usuario.id_usuario)}/dar_de_baja/')

    assert resp.status_code == 200
    usuario.refresh_from_db()
    socio.refresh_from_db()
    movil.refresh_from_db()
    assert usuario.estado == 'INACTIVO' and not usuario.sesion_actual
    assert socio.estado_socio == 'INACTIVO'
    assert socio.fecha_egreso == timezone.localdate()
    assert movil.estado_operativo == 'INACTIVO'
    assert FilaBase.objects.get(movil=movil).estado == 'RETIRADO'
    assert not UbicacionActual.objects.filter(movil=movil).exists()


@pytest.mark.django_db
def test_reactivar_la_cuenta_de_un_conductor_reactiva_al_socio_y_su_movil(autenticar, admin, conductor_completo):
    usuario, socio, movil = conductor_completo
    cliente = autenticar(admin)
    cliente.post(f'/api/usuarios/{int(usuario.id_usuario)}/dar_de_baja/')

    resp = cliente.post(f'/api/usuarios/{int(usuario.id_usuario)}/reactivar/')

    assert resp.status_code == 200
    usuario.refresh_from_db()
    socio.refresh_from_db()
    movil.refresh_from_db()
    assert usuario.estado == 'ACTIVO'
    assert socio.estado_socio == 'ACTIVO' and socio.fecha_egreso is None
    assert movil.estado_operativo == 'DISPONIBLE'
    # No lo devuelve a la fila.
    assert not FilaBase.objects.filter(movil=movil, estado__in=['EN_ESPERA', 'LLAMADO']).exists()


# ---------- baja de socio ----------

@pytest.mark.django_db
def test_solo_administrador_puede_dar_de_baja_socios(autenticar, crear_usuario, conductor_completo):
    _, socio, _ = conductor_completo
    central = crear_usuario('central_socio', rol_nombre='Central')

    resp = autenticar(central).post(f'/api/socios/{int(socio.id_socio)}/dar_de_baja/')

    assert resp.status_code == 403


@pytest.mark.django_db
def test_baja_de_socio_conserva_el_historial(autenticar, admin, conductor_completo):
    usuario, socio, movil = conductor_completo
    Solicitud.objects.create(origen='A', destino='B', movil=movil, estado='COMPLETADO')

    resp = autenticar(admin).post(f'/api/socios/{int(socio.id_socio)}/dar_de_baja/')

    assert resp.status_code == 200
    socio.refresh_from_db()
    usuario.refresh_from_db()
    movil.refresh_from_db()
    assert socio.estado_socio == 'INACTIVO'
    assert socio.fecha_egreso == timezone.localdate()
    assert usuario.estado == 'INACTIVO' and not usuario.sesion_actual
    assert movil.estado_operativo == 'INACTIVO'
    assert FilaBase.objects.get(movil=movil).estado == 'RETIRADO'
    assert not UbicacionActual.objects.filter(movil=movil).exists()
    # Nada se borra: viajes, socio y movil siguen ahi.
    assert Solicitud.objects.filter(movil=movil, estado='COMPLETADO').count() == 1
    assert Socio.objects.filter(pk=socio.pk).exists() and Movil.objects.filter(pk=movil.pk).exists()


@pytest.mark.django_db
def test_baja_de_socio_retira_tambien_a_un_movil_llamado(autenticar, admin, conductor_completo):
    _, socio, movil = conductor_completo
    FilaBase.objects.filter(movil=movil).update(estado='LLAMADO')

    autenticar(admin).post(f'/api/socios/{int(socio.id_socio)}/dar_de_baja/')

    assert FilaBase.objects.get(movil=movil).estado == 'RETIRADO'


@pytest.mark.django_db
def test_socio_con_viaje_en_curso_no_se_puede_dar_de_baja(autenticar, admin, conductor_completo):
    usuario, socio, movil = conductor_completo
    Solicitud.objects.create(origen='A', destino='B', movil=movil, estado='EN_CURSO')

    resp = autenticar(admin).post(f'/api/socios/{int(socio.id_socio)}/dar_de_baja/')

    assert resp.status_code == 409
    assert 'viaje en curso' in resp.data['detail']
    socio.refresh_from_db()
    usuario.refresh_from_db()
    assert socio.estado_socio == 'ACTIVO' and usuario.estado == 'ACTIVO'


@pytest.mark.django_db
def test_socio_sin_cuenta_se_puede_dar_de_baja(autenticar, admin, crear_socio):
    socio = crear_socio('22222222-2')

    resp = autenticar(admin).post(f'/api/socios/{int(socio.id_socio)}/dar_de_baja/')

    assert resp.status_code == 200
    socio.refresh_from_db()
    assert socio.estado_socio == 'INACTIVO'


@pytest.mark.django_db
def test_un_administrador_socio_no_puede_darse_de_baja_a_si_mismo(autenticar, admin, crear_socio):
    socio = crear_socio('33333333-3', usuario=admin)

    resp = autenticar(admin).post(f'/api/socios/{int(socio.id_socio)}/dar_de_baja/')

    assert resp.status_code == 409
    admin.refresh_from_db()
    assert admin.estado == 'ACTIVO'


@pytest.mark.django_db
def test_socio_ya_inactivo_es_409(autenticar, admin, crear_socio):
    socio = crear_socio('44444444-4')
    Socio.objects.filter(pk=socio.pk).update(estado_socio='INACTIVO')

    assert autenticar(admin).post(f'/api/socios/{int(socio.id_socio)}/dar_de_baja/').status_code == 409


@pytest.mark.django_db
def test_reactivar_socio_lo_deja_activo_y_su_movil_disponible(autenticar, admin, conductor_completo):
    usuario, socio, movil = conductor_completo
    cliente = autenticar(admin)
    cliente.post(f'/api/socios/{int(socio.id_socio)}/dar_de_baja/')

    resp = cliente.post(f'/api/socios/{int(socio.id_socio)}/reactivar/')

    assert resp.status_code == 200
    socio.refresh_from_db()
    usuario.refresh_from_db()
    movil.refresh_from_db()
    assert socio.estado_socio == 'ACTIVO' and socio.fecha_egreso is None
    assert usuario.estado == 'ACTIVO'
    assert movil.estado_operativo == 'DISPONIBLE'
    assert not FilaBase.objects.filter(movil=movil, estado__in=['EN_ESPERA', 'LLAMADO']).exists()


@pytest.mark.django_db
def test_reactivar_socio_con_bloqueo_vigente_lo_mantiene_bloqueado(autenticar, admin, conductor_completo):
    _, socio, movil = conductor_completo
    Bloqueo.objects.create(socio=socio, motivo='Cuota vencida', fecha_inicio=datetime.date.today(), activo=1)
    cliente = autenticar(admin)
    cliente.post(f'/api/socios/{int(socio.id_socio)}/dar_de_baja/')

    cliente.post(f'/api/socios/{int(socio.id_socio)}/reactivar/')

    socio.refresh_from_db()
    movil.refresh_from_db()
    assert socio.estado_socio == 'BLOQUEADO'
    assert movil.estado_operativo == 'BLOQUEADO'


@pytest.mark.django_db
def test_reactivar_socio_que_no_esta_inactivo_es_409(autenticar, admin, conductor_completo):
    _, socio, _ = conductor_completo

    assert autenticar(admin).post(f'/api/socios/{int(socio.id_socio)}/reactivar/').status_code == 409


@pytest.mark.django_db
def test_delete_de_socios_esta_deshabilitado(autenticar, admin, crear_socio):
    socio = crear_socio('55555555-5')

    resp = autenticar(admin).delete(f'/api/socios/{int(socio.id_socio)}/')

    assert resp.status_code == 405
    assert Socio.objects.filter(pk=socio.pk).exists()
