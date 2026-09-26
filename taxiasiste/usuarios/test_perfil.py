import pytest
from django.contrib.auth.hashers import check_password

URL = '/api/usuarios/mi_perfil/'


@pytest.mark.django_db
def test_ver_mi_perfil_de_personal(autenticar, crear_usuario):
    u = crear_usuario('per1', rol_nombre='Tesorero', email='per1@correo.cl', nombre='Ana', apellido='Rojas',
                      telefono='+56911112222')
    resp = autenticar(u).get(URL)
    assert resp.status_code == 200
    assert resp.data['username'] == 'per1'
    assert resp.data['rol'] == 'Tesorero'
    assert resp.data['nombre_completo'] == 'Ana Rojas'
    assert resp.data['telefono'] == '+56911112222'
    assert resp.data['es_socio'] is False
    assert resp.data['rut'] is None
    assert 'password' not in str(resp.data).lower().replace('password_', '')


@pytest.mark.django_db
def test_perfil_de_conductor_usa_los_datos_del_socio(autenticar, crear_usuario, crear_socio):
    u = crear_usuario('per2', rol_nombre='Conductor', email='per2@correo.cl')
    socio = crear_socio('12345678-9', nombre='Pedro', apellido='Soto', usuario=u)
    socio.telefono = '+56922223333'
    socio.save(update_fields=['telefono'])

    resp = autenticar(u).get(URL)

    assert resp.data['nombre_completo'] == 'Pedro Soto'
    assert resp.data['rut'] == '12345678-9'
    assert resp.data['telefono'] == '+56922223333'
    assert resp.data['es_socio'] is True


@pytest.mark.django_db
def test_requiere_sesion(client):
    assert client.get(URL).status_code == 401


@pytest.mark.django_db
def test_cambiar_telefono_normaliza_el_formato(autenticar, crear_usuario):
    u = crear_usuario('per3', rol_nombre='Central')
    resp = autenticar(u).patch(URL, {'telefono': '+56 9 1234-5678'})
    assert resp.status_code == 200
    assert resp.data['telefono'] == '+56912345678'
    u.refresh_from_db()
    assert u.telefono == '+56912345678'


@pytest.mark.django_db
def test_telefono_invalido_es_rechazado(autenticar, crear_usuario):
    u = crear_usuario('per4', rol_nombre='Central')
    resp = autenticar(u).patch(URL, {'telefono': 'abc123'})
    assert resp.status_code == 400


@pytest.mark.django_db
def test_telefono_de_conductor_se_guarda_en_su_socio(autenticar, crear_usuario, crear_socio):
    u = crear_usuario('per5', rol_nombre='Conductor')
    socio = crear_socio('11111111-1', usuario=u)

    autenticar(u).patch(URL, {'telefono': '912345678'})

    socio.refresh_from_db()
    u.refresh_from_db()
    assert socio.telefono == '912345678'
    assert u.telefono is None


@pytest.mark.django_db
def test_se_puede_borrar_el_telefono(autenticar, crear_usuario):
    u = crear_usuario('per6', rol_nombre='Central', telefono='912345678')
    resp = autenticar(u).patch(URL, {'telefono': ''})
    assert resp.status_code == 200 and resp.data['telefono'] is None


@pytest.mark.django_db
def test_cambiar_correo_exige_la_clave_actual(autenticar, crear_usuario):
    u = crear_usuario('per7', rol_nombre='Central', email='viejo7@correo.cl', password='Clave2026!')
    cliente = autenticar(u)

    sin_clave = cliente.patch(URL, {'email': 'nuevo7@correo.cl'})
    clave_mala = cliente.patch(URL, {'email': 'nuevo7@correo.cl', 'password_actual': 'otra'})

    assert sin_clave.status_code == 400 and clave_mala.status_code == 400
    u.refresh_from_db()
    assert u.email == 'viejo7@correo.cl'


@pytest.mark.django_db
def test_cambiar_correo_avisa_al_correo_anterior(autenticar, crear_usuario, mailoutbox):
    u = crear_usuario('per8', rol_nombre='Central', email='viejo8@correo.cl', password='Clave2026!')

    resp = autenticar(u).patch(URL, {'email': 'Nuevo8@Correo.cl', 'password_actual': 'Clave2026!'})

    assert resp.status_code == 200
    u.refresh_from_db()
    assert u.email == 'Nuevo8@Correo.cl'
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ['viejo8@correo.cl']
    assert 'Nuevo8@Correo.cl' in mailoutbox[0].body


@pytest.mark.django_db
def test_correo_ya_usado_por_otra_cuenta(autenticar, crear_usuario):
    crear_usuario('per9a', rol_nombre='Central', email='ocupado@correo.cl')
    u = crear_usuario('per9b', rol_nombre='Central', email='mio9@correo.cl', password='Clave2026!')

    resp = autenticar(u).patch(URL, {'email': 'OCUPADO@correo.cl', 'password_actual': 'Clave2026!'})

    assert resp.status_code == 400
    assert 'en uso' in resp.data['detail']


@pytest.mark.django_db
def test_mismo_correo_no_pide_clave_ni_avisa(autenticar, crear_usuario, mailoutbox):
    u = crear_usuario('per10', rol_nombre='Central', email='igual10@correo.cl')
    resp = autenticar(u).patch(URL, {'email': 'IGUAL10@correo.cl', 'telefono': '912345678'})
    assert resp.status_code == 200
    assert mailoutbox == []


@pytest.mark.django_db
def test_no_se_puede_cambiar_rol_ni_usuario_ni_estado(autenticar, crear_usuario):
    u = crear_usuario('per11', rol_nombre='Central')
    resp = autenticar(u).patch(URL, {'rol': 1, 'username': 'hackeado', 'estado': 'ACTIVO', 'id_rol': 1})
    assert resp.status_code == 200
    u.refresh_from_db()
    assert u.username == 'per11' and u.rol.nombre_rol == 'Central'


@pytest.mark.django_db
def test_correo_invalido(autenticar, crear_usuario):
    u = crear_usuario('per12', rol_nombre='Central', password='Clave2026!')
    resp = autenticar(u).patch(URL, {'email': 'no-es-correo', 'password_actual': 'Clave2026!'})
    assert resp.status_code == 400
    assert check_password('Clave2026!', u.password_hash)
