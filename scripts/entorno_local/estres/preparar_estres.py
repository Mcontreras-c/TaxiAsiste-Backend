"""Crea la base temporal taxiasiste_stress con 400 conductores, 100 usuarios de Central y 27 moviles en la fila.
No toca taxiasiste_dev ni taxiasiste_test. Las credenciales de PostgreSQL se leen del .env del backend (no se muestran).
Las cuentas de prueba usan una clave que solo existe en esa base temporal."""
import importlib.util
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
BACK = os.path.abspath(os.path.join(AQUI, '..', '..', '..'))
DB = 'taxiasiste_stress'
os.environ['POSTGRES_DB'] = DB

# reutiliza las funciones de preparar_bd.py (crear base, esquema, migraciones, migrate)
spec = importlib.util.spec_from_file_location('preparar_bd', os.path.join(AQUI, '..', 'preparar_bd.py'))
pb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pb)
if '--soltar' in sys.argv:
    pb.borrar(DB)
    print(f'base {DB} eliminada')
    sys.exit(0)
pb.preparar(DB, seed=False)

sys.path.insert(0, BACK)
sys.path.insert(0, AQUI)
os.environ['DJANGO_SETTINGS_MODULE'] = 'stress_settings'
os.chdir(BACK)
import django  # noqa: E402

django.setup()
from django.contrib.auth.hashers import make_password  # noqa: E402
from django.db import connection  # noqa: E402

NC, NV = 400, 100
h = make_password('Stress2026!')
with connection.cursor() as c:
    for nombre, desc in (('Administrador', 'Acceso total'), ('Central', 'Central telefonica'), ('Tesorero', 'Tesoreria'),
                         ('Conductor', 'Socio conductor'), ('Paletero', 'Paletero'), ('Secretario', 'Secretaria')):
        c.execute('INSERT INTO "ROLES" (id_rol, nombre_rol, descripcion, activo) VALUES (nextval(\'seq_roles\'), %s, %s, 1) '
                  'ON CONFLICT (nombre_rol) DO NOTHING', [nombre, desc])
    for i in range(1, NC + 1):
        u = f'stress_cond{i:03d}'
        c.execute('INSERT INTO "USUARIOS" (id_usuario, id_rol, username, password_hash, email, estado, fecha_creacion) '
                  'SELECT nextval(\'seq_usuarios\'), id_rol, %s, %s, %s, \'ACTIVO\', CURRENT_DATE FROM "ROLES" WHERE nombre_rol=\'Conductor\' '
                  'ON CONFLICT (username) DO NOTHING', [u, h, f'{u}@stress.test'])
        c.execute('INSERT INTO "SOCIOS" (id_socio, id_usuario, rut, nombre, apellido, telefono, direccion, estado_socio, fecha_ingreso) '
                  'SELECT nextval(\'seq_socios\'), id_usuario, %s, %s, %s, %s, %s, \'ACTIVO\', CURRENT_DATE FROM "USUARIOS" WHERE username=%s '
                  'ON CONFLICT (rut) DO NOTHING', [f'9{i:07d}-K', f'Cond{i}', 'Prueba', '911111111', 'Calle 1', u])
        c.execute('INSERT INTO "MOVILES" (id_movil, id_socio, patente, marca, modelo, anio, color, estado_operativo, fecha_registro) '
                  'SELECT nextval(\'seq_moviles\'), id_socio, %s, \'Toyota\', \'Corolla\', 2020, \'Blanco\', \'DISPONIBLE\', CURRENT_DATE '
                  'FROM "SOCIOS" WHERE rut=%s ON CONFLICT (patente) DO NOTHING', [f'ST{i:04d}', f'9{i:07d}-K'])
    for i in range(1, NV + 1):
        u = f'stress_central{i:03d}'
        c.execute('INSERT INTO "USUARIOS" (id_usuario, id_rol, username, password_hash, email, estado, fecha_creacion) '
                  'SELECT nextval(\'seq_usuarios\'), id_rol, %s, %s, %s, \'ACTIVO\', CURRENT_DATE FROM "ROLES" WHERE nombre_rol=\'Central\' '
                  'ON CONFLICT (username) DO NOTHING', [u, h, f'{u}@stress.test'])
    c.execute('UPDATE "USUARIOS" SET password_hash=%s WHERE username LIKE \'stress_%%\'', [h])
    c.execute('DELETE FROM "FILA_BASE"')
    c.execute('INSERT INTO "FILA_BASE" (id_fila, id_movil, posicion, estado) SELECT id_movil, id_movil, row_number() over (order by id_movil), '
              '\'EN_ESPERA\' FROM "MOVILES" ORDER BY id_movil LIMIT 27')
    c.execute('SELECT count(*) FROM "MOVILES"')
    print('moviles:', c.fetchone()[0])
    c.execute('SELECT count(*) FROM "USUARIOS"')
    print('usuarios:', c.fetchone()[0])
    c.execute('SELECT count(*) FROM "FILA_BASE"')
    print('en la fila:', c.fetchone()[0])
print('BASE DE ESTRES LISTA')
