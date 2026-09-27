"""Registro de quien hizo que (HISTORIAL_EVENTOS) en las acciones sensibles de administracion."""
import pytest

from taxiasiste.reportes.models import HistorialEvento

DATOS_CONDUCTOR = {
    'nombre': 'Ana', 'apellido': 'Rojas', 'rut': '11.111.111-1', 'email': 'ana.rojas@gmail.com',
    'vehiculo': {'patente': 'AB1234', 'marca': 'Toyota', 'modelo': 'Yaris'},
}


@pytest.fixture
def admin(crear_usuario, crear_rol):
    crear_rol('Conductor')
    return crear_usuario('admin_aud', rol_nombre='Administrador')


@pytest.fixture
def conductor(crear_usuario, crear_socio, crear_movil):
    usuario = crear_usuario('cond_aud', rol_nombre='Conductor', email='cond@gmail.com')
    socio = crear_socio('13131313-1', usuario=usuario)
    return usuario, socio, crear_movil(socio, 'AUD001')


def eventos(tipo, id_, evento=None):
    qs = HistorialEvento.objects.filter(entidad_tipo=tipo, entidad_id=id_)
    return qs.filter(evento=evento) if evento else qs


@pytest.mark.django_db
def test_crear_conductor_queda_registrado_con_quien_y_desde_donde(autenticar, admin):
    resp = autenticar(admin).post('/api/usuarios/crear_conductor/', DATOS_CONDUCTOR, format='json',
                                  HTTP_X_FORWARDED_FOR='200.1.2.3, 10.0.0.1')
    assert resp.status_code == 201

    ev = eventos('USUARIO', resp.data['usuario']['id_usuario'], 'CONDUCTOR_CREADO').get()
    assert ev.usuario_id == admin.pk and ev.ip_origen == '200.1.2.3'
    assert '11111111-1' in ev.detalle and 'AB1234' in ev.detalle and 'ana.rojas@gmail.com' in ev.detalle


@pytest.mark.django_db
def test_editar_registra_solo_los_campos_que_cambiaron(autenticar, admin, conductor):
    _, socio, _ = conductor
    autenticar(admin).patch(f'/api/socios/{socio.pk}/', {'telefono': '+56911112222', 'nombre': socio.nombre})

    ev = eventos('SOCIO', socio.pk, 'EDITADO').get()
    assert ev.usuario_id == admin.pk
    assert 'telefono: — → +56911112222' in ev.detalle and 'nombre' not in ev.detalle


@pytest.mark.django_db
def test_una_edicion_sin_cambios_no_deja_registro(autenticar, admin, conductor):
    _, socio, _ = conductor
    autenticar(admin).patch(f'/api/socios/{socio.pk}/', {'nombre': socio.nombre})
    assert not eventos('SOCIO', socio.pk).exists()


@pytest.mark.django_db
def test_bloqueo_baja_y_reactivacion_quedan_registrados(autenticar, admin, conductor):
    _, socio, _ = conductor
    client = autenticar(admin)

    client.post(f'/api/socios/{socio.pk}/bloquear/', {'motivo': 'Deuda'})
    client.post(f'/api/socios/{socio.pk}/desbloquear/')
    client.post(f'/api/socios/{socio.pk}/dar_de_baja/')
    client.post(f'/api/socios/{socio.pk}/reactivar/')

    assert list(eventos('SOCIO', socio.pk).order_by('id_evento').values_list('evento', flat=True)) == [
        'BLOQUEADO', 'DESBLOQUEADO', 'BAJA', 'REACTIVADO']
    assert 'Deuda' in eventos('SOCIO', socio.pk, 'BLOQUEADO').get().detalle


@pytest.mark.django_db
def test_bloquear_un_movil_se_registra_como_bloqueado(autenticar, admin, conductor):
    _, _, movil = conductor
    autenticar(admin).patch(f'/api/moviles/{movil.pk}/', {'estado_operativo': 'BLOQUEADO'})
    assert eventos('MOVIL', movil.pk, 'BLOQUEADO').count() == 1


@pytest.mark.django_db
def test_resetear_y_reenviar_registran_sin_guardar_la_clave(autenticar, admin, conductor):
    usuario, _, _ = conductor
    client = autenticar(admin)
    client.post(f'/api/usuarios/{usuario.pk}/resetear_password/', {'password_nueva': 'SuperSecreta9'})
    client.post(f'/api/usuarios/{usuario.pk}/reenviar_credenciales/')

    assert eventos('USUARIO', usuario.pk, 'CLAVE_RESETEADA').count() == 1
    assert eventos('USUARIO', usuario.pk, 'CREDENCIALES_REENVIADAS').count() == 1
    assert not HistorialEvento.objects.filter(detalle__contains='SuperSecreta9').exists()


@pytest.mark.django_db
def test_una_confirmacion_fallida_queda_registrada(autenticar, admin):
    autenticar(admin, confirmar=False).post('/api/usuarios/confirmar_identidad/', {'password': 'mala'})
    ev = eventos('USUARIO', admin.pk, 'CONFIRMACION_FALLIDA').get()
    assert ev.usuario_id == admin.pk


@pytest.mark.django_db
def test_lo_que_se_intenta_sin_confirmar_no_se_registra_como_hecho(autenticar, admin, conductor):
    _, socio, _ = conductor
    autenticar(admin, confirmar=False).post(f'/api/socios/{socio.pk}/dar_de_baja/')
    assert not eventos('SOCIO', socio.pk).exists()


@pytest.mark.django_db
def test_historial_de_una_persona_reune_cuenta_socio_y_vehiculo(autenticar, admin, conductor):
    usuario, socio, movil = conductor
    client = autenticar(admin)
    client.patch(f'/api/usuarios/{usuario.pk}/', {'email': 'nuevo.real@gmail.com'})
    client.patch(f'/api/socios/{socio.pk}/', {'telefono': '+56911112222'})
    client.patch(f'/api/moviles/{movil.pk}/', {'color': 'Rojo'})

    resp = client.get(f'/api/usuarios/{usuario.pk}/historial/')

    assert resp.status_code == 200
    assert {e['entidad_tipo'] for e in resp.data} == {'USUARIO', 'SOCIO', 'MOVIL'}
    assert resp.data[0]['usuario_nombre'] and 'ip_origen' in resp.data[0]


@pytest.mark.django_db
def test_solo_un_administrador_ve_el_historial(autenticar, crear_usuario, conductor):
    usuario, _, _ = conductor
    central = crear_usuario('central_aud', rol_nombre='Central')
    client = autenticar(central)
    assert client.get(f'/api/usuarios/{usuario.pk}/historial/').status_code == 403
    assert client.get('/api/historial/').status_code == 403


@pytest.mark.django_db
def test_un_fallo_al_registrar_no_impide_la_accion(autenticar, admin, conductor, monkeypatch):
    _, socio, _ = conductor
    monkeypatch.setattr(HistorialEvento, 'save', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom')))
    resp = autenticar(admin).post(f'/api/socios/{socio.pk}/bloquear/', {'motivo': 'x'})
    assert resp.status_code == 200
