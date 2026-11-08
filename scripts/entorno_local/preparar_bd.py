"""Prepara las bases PostgreSQL locales de TaxiAsiste (desarrollo y pruebas) de forma idempotente.

Uso (con el venv del backend):
    python scripts/entorno_local/preparar_bd.py              # crea/actualiza taxiasiste_dev y carga datos de demostracion
    python scripts/entorno_local/preparar_bd.py --reiniciar  # borra taxiasiste_dev y la deja como nueva
    python scripts/entorno_local/preparar_bd.py --test       # ademas prepara taxiasiste_test (para pytest)
    python scripts/entorno_local/preparar_bd.py --sin-seed   # no carga los datos de demostracion

Las credenciales se leen del .env del backend (POSTGRES_*); no se muestran en pantalla.
"""
import argparse
import os
import subprocess
import sys

import psycopg2
from decouple import Config, RepositoryEnv

BACK = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SQL = os.path.join(BACK, 'scripts')
ESQUEMA = 'create_business_schema_postgres'
MIGRACIONES = ['migrar_usuarios_nombre_apellido_postgres', 'migrar_usuarios_telefono_postgres',
               'migrar_solicitudes_origen_latlng_postgres', 'migrar_reservas_postgres',
               'migrar_fila_inactividad_llamado_postgres']
SEED = 'seed_datos_prueba_postgres'

env_path = os.path.join(BACK, '.env')
if not os.path.exists(env_path):
    sys.exit('Falta el archivo .env del backend. Copia .env.example a .env y completa POSTGRES_PASSWORD.')
cfg = Config(RepositoryEnv(env_path))
CON = dict(host=cfg('POSTGRES_HOST', default='localhost'), port=cfg('POSTGRES_PORT', default='5432'),
           user=cfg('POSTGRES_USER'), password=cfg('POSTGRES_PASSWORD'))


class conectar:
    """Conexion en modo autocommit (CREATE/DROP DATABASE no admiten transacciones) que se cierra al salir."""

    def __init__(self, db):
        self.c = psycopg2.connect(dbname=db, **CON)
        self.c.autocommit = True

    def __enter__(self):
        return self.c

    def __exit__(self, *a):
        self.c.close()


def existe(db):
    with conectar('postgres') as c:
        cur = c.cursor()
        cur.execute('SELECT 1 FROM pg_database WHERE datname=%s', (db,))
        return cur.fetchone() is not None


def crear(db):
    with conectar('postgres') as c:
        cur = c.cursor()
        cur.execute(f'CREATE DATABASE "{db}"')


def borrar(db):
    with conectar('postgres') as c:
        cur = c.cursor()
        cur.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()', (db,))
        cur.execute(f'DROP DATABASE IF EXISTS "{db}"')


def correr_sql(db, nombre):
    with conectar(db) as c:
        cur = c.cursor()
        cur.execute(open(os.path.join(SQL, nombre + '.sql'), encoding='utf-8').read())


def tiene_esquema(db):
    with conectar(db) as c:
        cur = c.cursor()
        cur.execute("SELECT to_regclass('public.\"USUARIOS\"') IS NOT NULL")
        return cur.fetchone()[0]


def preparar(db, seed, settings=None):
    if not existe(db):
        crear(db)
        print(f'  base {db}: creada')
    else:
        print(f'  base {db}: ya existe')
    if not tiene_esquema(db):
        correr_sql(db, ESQUEMA)
        print('  esquema de negocio: aplicado')
    for m in MIGRACIONES:            # todas idempotentes
        correr_sql(db, m)
    print('  migraciones SQL: al dia')
    if seed:
        correr_sql(db, SEED)
        print('  datos de demostracion: cargados (los existentes no se duplican)')
    envp = dict(os.environ, POSTGRES_DB=db, PYTHONUTF8='1')
    if settings:
        envp['DJANGO_SETTINGS_MODULE'] = settings
    r = subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput', '-v', '0'], cwd=BACK, env=envp)
    if r.returncode != 0:
        sys.exit('manage.py migrate fallo')
    print('  tablas internas de Django: al dia')
    with conectar(db) as c:
        cur = c.cursor()
        cuentas = []
        for t in ('USUARIOS', 'SOCIOS', 'MOVILES', 'PASAJEROS', 'SOLICITUDES'):
            cur.execute(f'SELECT count(*) FROM "{t}"')
            cuentas.append(f'{t.lower()}={cur.fetchone()[0]}')
    print('  contenido: ' + ', '.join(cuentas))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--reiniciar', action='store_true', help='borra y recrea la base de desarrollo')
    ap.add_argument('--sin-seed', action='store_true', help='no carga los datos de demostracion')
    ap.add_argument('--test', action='store_true', help='tambien prepara la base de pruebas (pytest)')
    a = ap.parse_args()
    dev = cfg('POSTGRES_DB', default='taxiasiste_dev')
    if a.reiniciar:
        borrar(dev)
        print(f'  base {dev}: eliminada para recrearla')
    print('Base de desarrollo')
    preparar(dev, seed=not a.sin_seed)
    if a.test:
        print('Base de pruebas')
        preparar(cfg('POSTGRES_TEST_DB', default='taxiasiste_test'), seed=False, settings='taxiasiste.settings_test')
    print('LISTO')
