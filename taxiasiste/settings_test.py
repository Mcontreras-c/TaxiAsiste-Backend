"""
Settings para pytest. Apunta a la base taxiasiste_test (ver
scripts/create_business_schema_postgres.sql) en vez de a taxiasiste_dev --
asi la suite nunca toca datos de desarrollo.

Por que no se usa el mecanismo normal de "base de datos de test" de Django:
todos los modelos de negocio son managed=False (el esquema se crea a mano
con SQL, no con migrations), asi que 'migrate' no crea ni una tabla de
negocio en una base de test nueva. En vez de eso, taxiasiste_test ya viene
con el esquema completo provisionado una vez (el mismo script SQL que
taxiasiste_dev), y conftest.py le dice a pytest-django que use esta conexion
directamente sin intentar crear ni destruir nada.
"""

from .settings import *  # noqa: F401,F403

DATABASES['default']['NAME'] = 'taxiasiste_test'
