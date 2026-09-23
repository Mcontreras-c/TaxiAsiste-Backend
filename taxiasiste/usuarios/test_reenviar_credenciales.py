import pytest
from django.contrib.auth.hashers import check_password


@pytest.mark.django_db
def test_solo_administrador_puede_reenviar(autenticar, crear_usuario):
    central = crear_usuario('cen1', rol_nombre='Central')
    objetivo = crear_usuario('obj1', email='obj1@correo.cl')
    resp = autenticar(central).post(f'/api/usuarios/{objetivo.pk}/reenviar_credenciales/')
    assert resp.status_code == 403


@pytest.mark.django_db
def test_reenvia_credenciales_a_conductor_con_link_de_app(autenticar, crear_usuario, mailoutbox, settings):
    settings.APK_DOWNLOAD_URL = 'https://expo.dev/build/xyz'
    admin = crear_usuario('adm1', rol_nombre='Administrador')
    conductor = crear_usuario('cond1', email='cond1@correo.cl', rol_nombre='Conductor', password='Vieja2026!')

    resp = autenticar(admin).post(f'/api/usuarios/{conductor.pk}/reenviar_credenciales/')

    assert resp.status_code == 200
    assert 'password' not in str(resp.data).lower().replace('credenciales', '')
    assert len(mailoutbox) == 1
    correo = mailoutbox[0]
    assert correo.to == ['cond1@correo.cl']
    assert 'https://expo.dev/build/xyz' in correo.body
    assert 'desinstalala' in correo.body
    assert 'cond1' in correo.body
    conductor.refresh_from_db()
    # la clave quedo cambiada y es la que viaja en el correo
    assert not check_password('Vieja2026!', conductor.password_hash)
    clave = next(l.split(': ', 1)[1] for l in correo.body.splitlines() if l.startswith('Contraseña: '))
    assert check_password(clave, conductor.password_hash)


@pytest.mark.django_db
def test_personal_administrativo_recibe_link_del_panel(autenticar, crear_usuario, mailoutbox, settings):
    settings.PANEL_WEB_URL = 'http://panel.test'
    settings.APK_DOWNLOAD_URL = 'https://expo.dev/build/xyz'
    admin = crear_usuario('adm2', rol_nombre='Administrador')
    tesorero = crear_usuario('tes1', email='tes1@correo.cl', rol_nombre='Tesorero')

    autenticar(admin).post(f'/api/usuarios/{tesorero.pk}/reenviar_credenciales/')

    body = mailoutbox[0].body
    assert 'http://panel.test' in body
    assert 'expo.dev' not in body


@pytest.mark.django_db
def test_sin_email_es_400_y_no_cambia_la_clave(autenticar, crear_usuario):
    admin = crear_usuario('adm3', rol_nombre='Administrador')
    sin_correo = crear_usuario('sc1', password='Igual2026!')
    resp = autenticar(admin).post(f'/api/usuarios/{sin_correo.pk}/reenviar_credenciales/')
    assert resp.status_code == 400
    sin_correo.refresh_from_db()
    assert check_password('Igual2026!', sin_correo.password_hash)


@pytest.mark.django_db
def test_si_falla_el_correo_se_conserva_la_clave_anterior(autenticar, crear_usuario, monkeypatch):
    monkeypatch.setattr('taxiasiste.usuarios.emails.send_mail', lambda *a, **k: (_ for _ in ()).throw(OSError('smtp caido')))
    admin = crear_usuario('adm4', rol_nombre='Administrador')
    u = crear_usuario('fallo1', email='fallo1@correo.cl', password='Igual2026!')

    resp = autenticar(admin).post(f'/api/usuarios/{u.pk}/reenviar_credenciales/')

    assert resp.status_code == 502
    u.refresh_from_db()
    assert check_password('Igual2026!', u.password_hash)
