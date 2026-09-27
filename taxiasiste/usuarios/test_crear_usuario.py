import pytest

from taxiasiste.socios.models import Socio
from taxiasiste.usuarios.models import Usuario


@pytest.mark.django_db
def test_no_administrador_no_puede_crear_usuario(autenticar, crear_usuario):
    central = crear_usuario('centralCrea1', rol_nombre='Central')
    client = autenticar(central)

    resp = client.post('/api/usuarios/', {
        'id_rol': central.rol_id, 'username': 'nuevo1', 'email': 'nuevo1@correo.cl',
    })

    assert resp.status_code == 403
    assert not Usuario.objects.filter(username='nuevo1').exists()


@pytest.mark.django_db
def test_crear_personal_del_sindicato(autenticar, crear_usuario, crear_rol, mailoutbox):
    admin = crear_usuario('adminCrea1', rol_nombre='Administrador')
    rol_tesorero = crear_rol('Tesorero')
    client = autenticar(admin)

    resp = client.post('/api/usuarios/', {
        'id_rol': rol_tesorero.pk,
        'username': 'cmunoz',
        'email': 'carolina.munoz@correo.cl',
        'nombre': 'Carolina',
        'apellido': 'Muñoz',
    })

    assert resp.status_code == 201, resp.data
    creado = Usuario.objects.get(username='cmunoz')
    assert creado.rol.nombre_rol == 'Tesorero'
    # La contrasena la genera el servidor -- nunca la manda el cliente ni
    # vuelve en la respuesta -- solo se entrega por correo.
    assert creado.password_hash
    assert 'password' not in resp.data
    # nombre_completo se arma con nombre/apellido propios (sin socio vinculado).
    assert resp.data['nombre_completo'] == 'Carolina Muñoz'
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ['carolina.munoz@correo.cl']
    assert 'cmunoz' in mailoutbox[0].body


@pytest.mark.django_db
def test_crear_usuario_sin_email_falla(autenticar, crear_usuario, crear_rol):
    admin = crear_usuario('adminCrea2', rol_nombre='Administrador')
    rol_central = crear_rol('Central')
    client = autenticar(admin)

    resp = client.post('/api/usuarios/', {'id_rol': rol_central.pk, 'username': 'sinemail'})

    assert resp.status_code == 400
    assert not Usuario.objects.filter(username='sinemail').exists()


@pytest.mark.django_db
def test_crear_conductor_vincula_al_socio_y_usa_su_nombre(autenticar, crear_usuario, crear_rol, crear_socio, mailoutbox):
    admin = crear_usuario('adminCrea3', rol_nombre='Administrador')
    rol_conductor = crear_rol('Conductor')
    socio = crear_socio('19191919-1', nombre='Juan', apellido='Soto')
    client = autenticar(admin)

    resp = client.post('/api/usuarios/', {
        'id_rol': rol_conductor.pk, 'username': 'jsoto', 'email': 'jsoto@correo.cl', 'id_socio': socio.pk,
    })

    assert resp.status_code == 201, resp.data
    socio.refresh_from_db()
    assert socio.usuario is not None
    assert socio.usuario.username == 'jsoto'
    # nombre_completo prioriza el nombre del Socio, no un nombre/apellido
    # propio de Usuario (que ademas ni se mando en el body).
    assert resp.data['nombre_completo'] == 'Juan Soto'
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_crear_conductor_con_socio_ya_vinculado_falla(autenticar, crear_usuario, crear_rol, crear_socio):
    admin = crear_usuario('adminCrea4', rol_nombre='Administrador')
    rol_conductor = crear_rol('Conductor')
    ya_vinculado = crear_usuario('yaTieneUsuario', rol_nombre='Conductor')
    socio = crear_socio('20202020-9', usuario=ya_vinculado)
    client = autenticar(admin)

    resp = client.post('/api/usuarios/', {
        'id_rol': rol_conductor.pk, 'username': 'otrousuario', 'email': 'otro@correo.cl', 'id_socio': socio.pk,
    })

    assert resp.status_code == 400
    assert not Usuario.objects.filter(username='otrousuario').exists()


@pytest.mark.django_db
def test_crear_conductor_con_socio_inexistente_falla(autenticar, crear_usuario, crear_rol):
    admin = crear_usuario('adminCrea5', rol_nombre='Administrador')
    rol_conductor = crear_rol('Conductor')
    client = autenticar(admin)

    resp = client.post('/api/usuarios/', {
        'id_rol': rol_conductor.pk, 'username': 'usuario2', 'email': 'usuario2@correo.cl', 'id_socio': 999999,
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
