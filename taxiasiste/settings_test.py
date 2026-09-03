"""
Settings para pytest. Apunta al esquema Oracle dedicado taxiasiste_test (ver
scripts/setup_test_schema.sql) en vez de al de taxiasiste_app -- asi la
suite nunca toca datos de desarrollo.

Por que no se usa el mecanismo normal de "base de datos de test" de Django:
todos los modelos de negocio son managed=False (el esquema se crea a mano
con SQL, no con migrations), asi que 'migrate' no crea ni una tabla de
negocio en una base de test nueva. Ademas el usuario de la app (taxiasiste_app)
no tiene privilegios para CREATE USER, que es lo que Django necesita para
crear/destruir esa base de test en Oracle en cada corrida. En vez de eso,
taxiasiste_test ya viene con el esquema completo provisionado una vez (los
mismos scripts SQL que taxiasiste_app), y conftest.py le dice a pytest-django
que use esta conexion directamente sin intentar crear ni destruir nada.
"""

from decouple import config

from .settings import *  # noqa: F401,F403

DATABASES['default']['USER'] = config('ORACLE_TEST_USER')
DATABASES['default']['PASSWORD'] = config('ORACLE_TEST_PASSWORD')
