"""Respaldo y restauracion de prueba de la base de datos local de TaxiAsiste.

Uso (con el venv del backend):
    python scripts/entorno_local/respaldo_local.py                 # respalda la base de desarrollo y la carpeta media
    python scripts/entorno_local/respaldo_local.py --probar        # respalda, restaura en una base temporal y compara registros
    python scripts/entorno_local/respaldo_local.py --destino D:\\respaldos   # otra carpeta (por ejemplo, un pendrive)

Genera en la carpeta de destino (por defecto <carpeta de los proyectos>\\respaldos):
    taxiasiste_YYYYMMDD_HHMM.dump       volcado de PostgreSQL (formato personalizado de pg_dump)
    media_YYYYMMDD_HHMM.zip             documentos subidos (agenda)
Conserva los ultimos 7 dias. Las credenciales se leen del .env del backend y no se muestran.
"""
import argparse
import datetime as dt
import glob
import os
import subprocess
import sys
import zipfile

import psycopg2
from decouple import Config, RepositoryEnv

BACK = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
cfg = Config(RepositoryEnv(os.path.join(BACK, '.env')))
HOST = cfg('POSTGRES_HOST', default='localhost')
PORT = cfg('POSTGRES_PORT', default='5432')
USER = cfg('POSTGRES_USER')
PWD = cfg('POSTGRES_PASSWORD')
DB = cfg('POSTGRES_DB', default='taxiasiste_dev')
TABLAS = ['ROLES', 'USUARIOS', 'SOCIOS', 'MOVILES', 'CUOTAS', 'BLOQUEOS', 'TESORERIA_MOVIMIENTOS', 'FILA_BASE', 'UBICACION_ACTUAL',
          'PASAJEROS', 'SOLICITUDES', 'RESERVAS', 'RESERVA_EVENTOS', 'HISTORIAL_EVENTOS', 'EVENTOS_AGENDA', 'DOCUMENTOS_AGENDA']
RETENCION_DIAS = 7


def binario(nombre):
    for base in sorted(glob.glob(r'C:\Program Files\PostgreSQL\*\bin'), reverse=True):
        ruta = os.path.join(base, nombre + '.exe')
        if os.path.exists(ruta):
            return ruta
    return nombre   # confia en el PATH


class conectar:
    """Conexion en autocommit (CREATE/DROP DATABASE no admiten transacciones) que se cierra al salir."""

    def __init__(self, db):
        self.c = psycopg2.connect(host=HOST, port=PORT, user=USER, password=PWD, dbname=db)
        self.c.autocommit = True

    def __enter__(self):
        return self.c

    def __exit__(self, *a):
        self.c.close()


def conteos(db):
    with conectar(db) as c:
        cur = c.cursor()
        out = {}
        for t in TABLAS:
            cur.execute(f'SELECT count(*) FROM "{t}"')
            out[t] = cur.fetchone()[0]
        return out


def respaldar(destino):
    os.makedirs(destino, exist_ok=True)
    sello = dt.datetime.now().strftime('%Y%m%d_%H%M')
    dump = os.path.join(destino, f'taxiasiste_{sello}.dump')
    parcial = dump + '.parcial'
    env = dict(os.environ, PGPASSWORD=PWD)
    r = subprocess.run([binario('pg_dump'), '-h', HOST, '-p', PORT, '-U', USER, '-Fc', '-f', parcial, DB], env=env, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit('pg_dump fallo: ' + r.stderr.strip()[:300])
    # verificacion: el archivo debe poder listarse con pg_restore
    v = subprocess.run([binario('pg_restore'), '-l', parcial], env=env, capture_output=True, text=True)
    if v.returncode != 0 or not v.stdout.strip():
        sys.exit('el respaldo no paso la verificacion (pg_restore -l)')
    os.replace(parcial, dump)
    media = os.path.join(BACK, 'media')
    zpath = os.path.join(destino, f'media_{sello}.zip')
    n = 0
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for raiz, _, archivos in os.walk(media):
            for f in archivos:
                ruta = os.path.join(raiz, f)
                z.write(ruta, os.path.relpath(ruta, media))
                n += 1
    limite = dt.datetime.now() - dt.timedelta(days=RETENCION_DIAS)
    borrados = 0
    for f in glob.glob(os.path.join(destino, 'taxiasiste_*.dump')) + glob.glob(os.path.join(destino, 'media_*.zip')):
        if dt.datetime.fromtimestamp(os.path.getmtime(f)) < limite:
            os.remove(f)
            borrados += 1
    print(f'Respaldo de la base: {dump} ({os.path.getsize(dump) // 1024} KB)')
    print(f'Respaldo de documentos: {zpath} ({n} archivos)')
    print(f'Respaldos antiguos eliminados (> {RETENCION_DIAS} dias): {borrados}')
    return dump


def probar_restauracion(dump):
    temporal = 'taxiasiste_restauracion'
    env = dict(os.environ, PGPASSWORD=PWD)
    with conectar('postgres') as c:
        cur = c.cursor()
        cur.execute(f'DROP DATABASE IF EXISTS "{temporal}"')
        cur.execute(f'CREATE DATABASE "{temporal}"')
    try:
        r = subprocess.run([binario('pg_restore'), '-h', HOST, '-p', PORT, '-U', USER, '-d', temporal, '--no-owner', dump], env=env, capture_output=True, text=True)
        if r.returncode not in (0, 1):
            sys.exit('pg_restore fallo: ' + r.stderr.strip()[:300])
        a, b = conteos(DB), conteos(temporal)
        print(f'\nComparacion de registros: base original ({DB}) vs restaurada ({temporal})')
        print(f'{"Tabla":28}{"Original":>10}{"Restaurada":>12}  Resultado')
        ok = True
        for t in TABLAS:
            igual = a[t] == b[t]
            ok &= igual
            print(f'{t:28}{a[t]:>10}{b[t]:>12}  {"IGUAL" if igual else "DIFERENTE"}')
        print('\nRESULTADO: ' + ('la restauracion es identica al original' if ok else 'HAY DIFERENCIAS'))
        return ok
    finally:
        with conectar('postgres') as c:
            c.cursor().execute(f'DROP DATABASE IF EXISTS "{temporal}"')
        print(f'Base temporal {temporal} eliminada.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--probar', action='store_true', help='restaura en una base temporal y compara los registros')
    ap.add_argument('--destino', default=os.path.join(os.path.dirname(BACK), 'respaldos'))
    a = ap.parse_args()
    d = respaldar(a.destino)
    if a.probar and not probar_restauracion(d):
        sys.exit(1)
