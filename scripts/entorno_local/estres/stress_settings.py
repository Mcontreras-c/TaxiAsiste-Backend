"""Configuracion SOLO para la prueba de estres local (no se sube al repositorio).
Apunta a la base taxiasiste_stress y usa un hasher barato para que los inicios de sesion de la rampa no dominen la CPU
(los inicios de sesion se excluyen de las metricas de todos modos)."""
import os

os.environ['POSTGRES_DB'] = 'taxiasiste_stress'
os.environ['DEBUG'] = 'False'

from taxiasiste.settings import *  # noqa: F401,F403,E402

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
if os.environ.get('STRESS_PERSISTENTE') == '1':
    DATABASES['default']['CONN_MAX_AGE'] = 60
