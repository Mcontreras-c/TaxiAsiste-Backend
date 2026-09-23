import pytest
from django.contrib.auth.hashers import check_password

from taxiasiste.socios.models import Socio
from taxiasiste.usuarios.models import Usuario


@pytest.mark.django_db
def test_no_administrador_no_puede_crear_usuario(autenticar, crear_usuario):
    central = crear_usuario('centralCrea1', rol_nombre='Central')
    client = autenticar(central)

    resp = client.post('/api/usuarios/', {
        'id_rol': central.rol_id, 'username': 'nuevo1', 'password': 'Clave123',
    })

    assert resp.status_code == 403
    assert not Usuario.objects.filter(username='nuevo1').exists()


@pytest.mark.django_db
def test_crear_personal_del_sindicato(autenticar, crear_usuario, crear_rol):
    admin = crear_usuario('adminCrea1', rol_nombre='Administrador')
    rol_tesorero = crear_rol('Tesorero')
    client = autenticar(admin)

    resp = client.post('/api/usuarios/', {
        'id_rol': rol_tesorero.pk,
        'username': 'cmunoz',
        'email': 'carolina.munoz@example.cl',
        'nombre': 'Carolina',
        'apellido': 'Muñoz',
        'password': 'Clave123',
    })

    assert resp.status_code == 201, resp.data
    creado = Usuario.objects.get(username='cmunoz')
    assert creado.rol.nombre_rol == 'Tesorero'
    assert check_password('Clave123', creado.password_hash)
    # nombre_completo se arma con nombre/apellido propios (sin socio vinculado).
    assert resp.data['nombre_completo'] == 'Carolina Muñoz'
    # password nunca vuelve en la respuesta.
    assert 'password' not in resp.data


@pytest.mark.django_db
def test_crear_usuario_sin_password_falla(autenticar, crear_usuario, crear_rol):
    admin = crear_usuario('adminCrea2', rol_nombre='Administrador')
    rol_central = crear_rol('Central')
    client = autenticar(admin)

    resp = client.post('/api/usuarios/', {'id_rol': rol_central.pk, 'username': 'sinpass'})

    assert resp.status_code == 400
    assert not Usuario.objects.filter(username='sinpass').exists()


@pytest.mark.django_db
def test_crear_conductor_vincula_al_socio_y_usa_su_nombre(autenticar, crear_usuario, crear_rol, crear_socio):
    admin = crear_usuario('adminCrea3', rol_nombre='Administrador')
    rol_conductor = crear_rol('Conductor')
    socio = crear_socio('19191919-1', nombre='Juan', apellido='Soto')
    client = autenticar(admin)

    resp = client.post('/api/usuarios/', {
        'id_rol': rol_conductor.pk, 'username': 'jsoto', 'password': 'Clave123', 'id_socio': socio.pk,
    })

    assert resp.status_code == 201, resp.data
    socio.refresh_from_db()
    assert socio.usuario is not None
    assert socio.usuario.username == 'jsoto'
    # nombre_completo prioriza el nombre del Socio, no un nombre/apellido
    # propio de Usuario (que ademas ni se mando en el body).
    assert resp.data['nombre_completo'] == 'Juan Soto'


@pytest.mark.django_db
def test_crear_conductor_con_socio_ya_vinculado_falla(autenticar, crear_usuario, crear_rol, crear_socio):
    admin = crear_usuario('adminCrea4', rol_nombre='Administrador')
    rol_conductor = crear_rol('Conductor')
    ya_vinculado = crear_usuario('yaTieneUsuario', rol_nombre='Conductor')
    socio = crear_socio('20202020-9', usuario=ya_vinculado)
    client = autenticar(admin)

    resp = client.post('/api/usuarios/', {
        'id_rol': rol_conductor.pk, 'username': 'otrousuario', 'password': 'Clave123', 'id_socio': socio.pk,
    })

    assert resp.status_code == 400
    assert not Usuario.objects.filter(username='otrousuario').exists()


@pytest.mark.django_db
def test_crear_conductor_con_socio_inexistente_falla(autenticar, crear_usuario, crear_rol):
    admin = crear_usuario('adminCrea5', rol_nombre='Administrador')
    rol_conductor = crear_rol('Conductor')
    client = autenticar(admin)

    resp = client.post('/api/usuarios/', {
        'id_rol': rol_conductor.pk, 'username': 'usuario2', 'password': 'Clave123', 'id_socio': 999999,
    })

    assert resp.status_code == 400
    assert not Usuario.objects.filter(username='usuario2').exists()


@pytest.mark.django_db
def test_listado_muestra_nombre_completo_del_socio_para_conductores(autenticar, crear_usuario, crear_socio):
    admin = crear_usuario('adminCrea6', rol_nombre='Administrador')
    conductor = crear_usuario('karla', rol_nombre='Conductor')
    crear_socio('21212121-k', nombre='Karla', apellido='Fuentes', usuario=conductor)
    client = autenticar(admin)

    resp = client.get('/api/usuarios/')

    assert resp.status_code == 200
    item = next(u for u in resp.data if u['id_usuario'] == conductor.id_usuario)
    assert item['nombre_completo'] == 'Karla Fuentes'


@pytest.mark.django_db
def test_nombre_completo_cae_al_username_sin_socio_ni_nombre(autenticar, crear_usuario):
    admin = crear_usuario('adminCrea7', rol_nombre='Administrador')
    sin_datos = crear_usuario('sindatos', rol_nombre='Central')
    client = autenticar(admin)

    resp = client.get('/api/usuarios/')

    assert resp.status_code == 200
    item = next(u for u in resp.data if u['id_usuario'] == sin_datos.id_usuario)
    assert item['nombre_completo'] == 'sindatos'
