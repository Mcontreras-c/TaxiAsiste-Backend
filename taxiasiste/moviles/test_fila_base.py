import pytest
from taxiasiste.moviles.models import FilaBase


@pytest.fixture
def movil_a(crear_socio, crear_movil):
    return crear_movil(crear_socio('22222222-2'), 'AAAA11')


@pytest.fixture
def movil_b(crear_socio, crear_movil):
    return crear_movil(crear_socio('33333333-3'), 'BBBB22')


@pytest.mark.django_db
def test_entrar_a_fila_asigna_posicion_incremental(autenticar, crear_usuario, movil_a, movil_b):
    conductor = crear_usuario('conductorA', rol_nombre='Conductor')
    client = autenticar(conductor)

    r1 = client.post('/api/fila-base/', {'movil': movil_a.id_movil})
    r2 = client.post('/api/fila-base/', {'movil': movil_b.id_movil})

    assert r1.status_code == 201 and r1.data['posicion'] == 1
    assert r2.status_code == 201 and r2.data['posicion'] == 2


@pytest.mark.django_db
def test_no_permite_doble_entrada_del_mismo_movil(autenticar, crear_usuario, movil_a):
    conductor = crear_usuario('conductorB', rol_nombre='Conductor')
    client = autenticar(conductor)
    client.post('/api/fila-base/', {'movil': movil_a.id_movil})

    resp = client.post('/api/fila-base/', {'movil': movil_a.id_movil})

    assert resp.status_code == 400


@pytest.mark.django_db
def test_listado_por_defecto_solo_muestra_en_espera(autenticar, crear_usuario, movil_a, movil_b):
    conductor = crear_usuario('conductorC', rol_nombre='Conductor')
    client = autenticar(conductor)
    entrada_a = client.post('/api/fila-base/', {'movil': movil_a.id_movil}).data
    client.post('/api/fila-base/', {'movil': movil_b.id_movil})
    client.post(f"/api/fila-base/{entrada_a['id_fila']}/llamar/")

    resp = client.get('/api/fila-base/')

    patentes = [e['patente'] for e in resp.data]
    assert 'AAAA11' not in patentes
    assert 'BBBB22' in patentes


@pytest.mark.django_db
def test_llamar_una_entrada_llamado_no_se_puede_re_llamar(autenticar, crear_usuario, movil_a):
    """Con ?todos=1 (ver get_queryset) la entrada LLAMADO sigue siendo
    encontrable via retrieve/accion puntual, aunque el listado la excluya."""
    conductor = crear_usuario('conductorD', rol_nombre='Conductor')
    client = autenticar(conductor)
    entrada = client.post('/api/fila-base/', {'movil': movil_a.id_movil}).data

    primero = client.post(f"/api/fila-base/{entrada['id_fila']}/llamar/")
    segundo = client.post(f"/api/fila-base/{entrada['id_fila']}/llamar/")

    assert primero.status_code == 200 and primero.data['estado'] == 'LLAMADO'
    assert segundo.status_code == 400


@pytest.mark.django_db
def test_retirar_libera_al_movil_para_volver_a_entrar(autenticar, crear_usuario, movil_a):
    conductor = crear_usuario('conductorE', rol_nombre='Conductor')
    client = autenticar(conductor)
    entrada = client.post('/api/fila-base/', {'movil': movil_a.id_movil}).data
    client.post(f"/api/fila-base/{entrada['id_fila']}/retirar/")

    resp = client.post('/api/fila-base/', {'movil': movil_a.id_movil})

    assert resp.status_code == 201
    assert FilaBase.objects.filter(movil=movil_a, estado='EN_ESPERA').count() == 1
