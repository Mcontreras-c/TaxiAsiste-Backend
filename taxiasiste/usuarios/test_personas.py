"""Confirmacion con contrasena (step-up) y alta unificada de conductores."""
import pytest
from django.test import override_settings

from taxiasiste.moviles.models import Movil
from taxiasiste.socios.models import Socio
from taxiasiste.usuarios.models import Usuario

CLAVE = 'Test2026!'


@pytest.fixture
def admin(crear_usuario, crear_rol):
    crear_rol('Conductor')
    return crear_usuario('admin_pers', rol_nombre='Administrador')


@pytest.fixture
def conductor(crear_usuario, crear_socio, crear_movil):
    usuario = crear_usuario('cond_pers', rol_nombre='Conductor')
    socio = crear_socio('13131313-1', usuario=usuario)
    return socio, crear_movil(socio, 'PERS01')


def datos_conductor(**cambios):
    datos = {
        'nombre': 'Ana', 'apellido': 'Rojas Díaz', 'rut': '11.111.111-1', 'email': 'ana.rojas@gmail.com',
        'telefono': '+56 9 1234 5678',
        'vehiculo': {'patente': 'ab-1234', 'marca': 'Toyota', 'modelo': 'Yaris', 'anio': 2018, 'color': 'Negro'},
    }
    datos.update(cambios)
    return datos


# ── Confirmacion con contrasena ──────────────────────────────────────────────
@pytest.mark.django_db
def test_confirmar_identidad_con_la_clave_correcta_entrega_un_permiso(autenticar, admin):
    resp = autenticar(admin, confirmar=False).post('/api/usuarios/confirmar_identidad/', {'password': CLAVE})
    assert resp.status_code == 200 and resp.data['token']


@pytest.mark.django_db
def test_confirmar_identidad_con_clave_incorrecta_falla(autenticar, admin):
    resp = autenticar(admin, confirmar=False).post('/api/usuarios/confirmar_identidad/', {'password': 'mala'})
    assert resp.status_code == 400 and 'token' not in resp.data


@pytest.mark.django_db
def test_cinco_claves_incorrectas_bloquean_incluso_la_correcta(autenticar, admin):
    client = autenticar(admin, confirmar=False)
    for _ in range(5):
        client.post('/api/usuarios/confirmar_identidad/', {'password': 'mala'})
    resp = client.post('/api/usuarios/confirmar_identidad/', {'password': CLAVE})
    assert resp.status_code == 429


@pytest.mark.django_db
def test_sin_permiso_las_acciones_sensibles_se_rechazan(autenticar, admin, conductor):
    socio, movil = conductor
    client = autenticar(admin, confirmar=False)
    assert client.post(f'/api/socios/{socio.pk}/dar_de_baja/').status_code == 403
    assert client.post(f'/api/socios/{socio.pk}/bloquear/', {'motivo': 'x'}).status_code == 403
    assert client.patch(f'/api/socios/{socio.pk}/', {'telefono': '+56911111111'}).status_code == 403
    assert client.patch(f'/api/moviles/{movil.pk}/', {'estado_operativo': 'BLOQUEADO'}).status_code == 403
    assert client.post(f'/api/usuarios/{socio.usuario_id}/resetear_password/', {'password_nueva': 'abcdef'}).status_code == 403
    socio.refresh_from_db()
    assert socio.estado_socio == 'ACTIVO'


@pytest.mark.django_db
def test_un_permiso_vencido_no_sirve(autenticar, admin, conductor):
    socio, _ = conductor
    client = autenticar(admin)
    with override_settings(CONFIRMACION_SEGUNDOS=-1):
        assert client.post(f'/api/socios/{socio.pk}/bloquear/', {'motivo': 'x'}).status_code == 403


@pytest.mark.django_db
def test_el_permiso_no_sirve_para_otra_persona_ni_otra_sesion(autenticar, admin, crear_usuario, conductor):
    from taxiasiste.usuarios.confirmacion import emitir_token

    socio, _ = conductor
    otro = crear_usuario('admin_otro', rol_nombre='Administrador')
    token_ajeno = emitir_token(otro)
    client = autenticar(admin, confirmar=False)
    client.credentials(**{**client._credentials, 'HTTP_X_CONFIRMACION': token_ajeno})
    assert client.post(f'/api/socios/{socio.pk}/bloquear/', {'motivo': 'x'}).status_code == 403

    # Mismo usuario pero otra sesion (login nuevo): el permiso anterior deja de valer
    token_viejo = emitir_token(admin)
    client = autenticar(admin, sid='sesion-nueva', confirmar=False)
    client.credentials(**{**client._credentials, 'HTTP_X_CONFIRMACION': token_viejo})
    assert client.post(f'/api/socios/{socio.pk}/bloquear/', {'motivo': 'x'}).status_code == 403


@pytest.mark.django_db
def test_con_permiso_la_accion_funciona(autenticar, admin, conductor):
    socio, _ = conductor
    resp = autenticar(admin).post(f'/api/socios/{socio.pk}/bloquear/', {'motivo': 'x'})
    assert resp.status_code == 200


@pytest.mark.django_db
def test_las_acciones_operativas_del_movil_no_piden_confirmacion(autenticar, conductor):
    socio, movil = conductor
    resp = autenticar(socio.usuario, confirmar=False).post(f'/api/moviles/{movil.pk}/desconectar/')
    assert resp.status_code == 200


# ── Alta unificada de conductor ──────────────────────────────────────────────
@pytest.mark.django_db
def test_crear_conductor_crea_socio_vehiculo_y_cuenta_y_manda_credenciales(autenticar, admin, mailoutbox):
    resp = autenticar(admin).post('/api/usuarios/crear_conductor/', datos_conductor(), format='json')

    assert resp.status_code == 201, resp.data
    usuario = Usuario.objects.get(email='ana.rojas@gmail.com')
    socio = Socio.objects.get(rut='11111111-1')
    movil = Movil.objects.get(patente='AB1234')
    assert usuario.rol.nombre_rol == 'Conductor' and usuario.username == 'arojas'
    assert socio.usuario_id == usuario.pk and movil.socio_id == socio.pk
    assert socio.telefono == '+56912345678'
    assert resp.data['correo_enviado'] is True and 'password' not in str(resp.data)
    assert len(mailoutbox) == 1 and mailoutbox[0].to == ['ana.rojas@gmail.com']


@pytest.mark.django_db
def test_crear_conductor_es_todo_o_nada(autenticar, admin, crear_socio, crear_movil):
    otro = crear_socio('22222222-2')
    crear_movil(otro, 'AB1234')  # patente ya usada

    resp = autenticar(admin).post('/api/usuarios/crear_conductor/', datos_conductor(), format='json')

    assert resp.status_code == 400
    assert not Usuario.objects.filter(email='ana.rojas@gmail.com').exists()
    assert not Socio.objects.filter(rut='11111111-1').exists()


@pytest.mark.django_db
@pytest.mark.parametrize('cambios,campo', [
    ({'email': 'ana@example.cl'}, 'email'),                 # dominio de prueba
    ({'email': 'no-es-un-correo'}, 'email'),
    ({'rut': '11.111.111-9'}, 'rut'),                        # digito verificador malo
    ({'telefono': '123'}, 'telefono'),
    ({'vehiculo': {'patente': 'ZZZ', 'marca': 'a', 'modelo': 'b'}}, 'vehiculo'),
])
def test_crear_conductor_rechaza_datos_invalidos(autenticar, admin, cambios, campo):
    resp = autenticar(admin).post('/api/usuarios/crear_conductor/', datos_conductor(**cambios), format='json')
    assert resp.status_code == 400 and campo in resp.data


@pytest.mark.django_db
def test_crear_conductor_rechaza_correo_o_rut_repetidos(autenticar, admin, crear_usuario, crear_socio):
    crear_usuario('previo', rol_nombre='Central', email='Ana.Rojas@gmail.com')
    crear_socio('11111111-1')
    client = autenticar(admin)

    assert client.post('/api/usuarios/crear_conductor/', datos_conductor(), format='json').status_code == 400
    resp = client.post('/api/usuarios/crear_conductor/', datos_conductor(email='otra@gmail.com'), format='json')
    assert resp.status_code == 400 and 'rut' in resp.data


@pytest.mark.django_db
def test_solo_un_administrador_crea_conductores(autenticar, crear_usuario):
    central = crear_usuario('central_pers', rol_nombre='Central')
    resp = autenticar(central).post('/api/usuarios/crear_conductor/', datos_conductor(), format='json')
    assert resp.status_code == 403


@pytest.mark.django_db
def test_el_username_generado_no_choca_con_uno_existente(autenticar, admin, crear_usuario):
    crear_usuario('arojas', rol_nombre='Central')
    resp = autenticar(admin).post('/api/usuarios/crear_conductor/', datos_conductor(), format='json')
    assert resp.status_code == 201
    assert Usuario.objects.get(email='ana.rojas@gmail.com').username == 'arojas2'


@pytest.mark.django_db
def test_editar_una_cuenta_con_correo_generico_no_obliga_a_cambiarlo(autenticar, admin, crear_usuario):
    vieja = crear_usuario('vieja', rol_nombre='Central', email='vieja@example.cl')
    client = autenticar(admin)

    assert client.patch(f'/api/usuarios/{vieja.pk}/', {'nombre': 'Vieja'}).status_code == 200
    # ...pero un correo nuevo si tiene que ser real
    assert client.patch(f'/api/usuarios/{vieja.pk}/', {'email': 'otra@example.cl'}).status_code == 400
    assert client.patch(f'/api/usuarios/{vieja.pk}/', {'email': 'vieja.real@gmail.com'}).status_code == 200
