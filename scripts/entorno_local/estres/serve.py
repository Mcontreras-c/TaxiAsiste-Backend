"""Levanta el backend con waitress (3 hilos) y muestrea su CPU cada segundo en un CSV."""
import os
import sys
import threading
import time

import psutil

AQUI = os.path.dirname(os.path.abspath(__file__))
BACK = os.path.abspath(os.path.join(AQUI, '..', '..', '..'))
sys.path.insert(0, BACK)
sys.path.insert(0, AQUI)
os.environ['DJANGO_SETTINGS_MODULE'] = 'stress_settings'
os.chdir(BACK)

from waitress import serve  # noqa: E402

from taxiasiste.wsgi import application  # noqa: E402

salida = sys.argv[1]


def muestreo():
    p = psutil.Process()
    p.cpu_percent(None)
    psutil.cpu_percent(None)
    with open(salida, 'w') as f:
        f.write('t,cpu_proceso,cpu_total\n')
        while True:
            time.sleep(1)
            f.write(f'{time.time():.1f},{p.cpu_percent(None):.1f},{psutil.cpu_percent(None):.1f}\n')
            f.flush()


threading.Thread(target=muestreo, daemon=True).start()
serve(application, host='127.0.0.1', port=8765, threads=3, connection_limit=1000, backlog=1024)
