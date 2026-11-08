import csv
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable                                          # el python del venv del backend
LOCUST = os.path.join(os.path.dirname(PY), 'locust.exe')
DURACION = int(os.environ.get('STRESS_DURACION', '90'))   # segundos por etapa (90 en el informe)
VENTANA_DESDE = 30 if DURACION >= 60 else DURACION // 3   # s desde el inicio: se descartan la rampa y el desfase inicial


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p / 100))] if v else None


def esperar_servidor():
    for _ in range(60):
        try:
            urllib.request.urlopen('http://127.0.0.1:8765/api/ping/', timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def correr(config, mult):
    persistente = config == 'B'
    env = dict(os.environ, PYTHONUTF8='1', STRESS_PERSISTENTE='1' if persistente else '0')
    cpu_csv = os.path.join(AQUI, f'cpu_{config}_{mult}x.csv')
    raw = os.path.join(AQUI, f'raw_{config}_{mult}x.csv')
    srv = subprocess.Popen([PY, os.path.join(AQUI, 'serve.py'), cpu_csv], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not esperar_servidor():
            return {'error': 'servidor no levanto'}
        # calentamiento ligero (importa modulos, abre conexiones)
        for _ in range(5):
            try:
                urllib.request.urlopen('http://127.0.0.1:8765/api/ping/', timeout=2)
            except Exception:
                pass
        usuarios = 125 * mult
        env2 = dict(env, STRESS_RAW=raw)
        t_ini = time.time()
        subprocess.run([LOCUST, '-f', os.path.join(AQUI, 'locustfile.py'), '--headless', '-u', str(usuarios), '-r', str(usuarios // 8),
                        '-t', f'{DURACION}s', '--host', 'http://127.0.0.1:8765', '--only-summary'],
                       env=env2, cwd=AQUI, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=DURACION + 120)
        t_fin = time.time()
    finally:
        srv.terminate()
        try:
            srv.wait(10)
        except Exception:
            srv.kill()
    filas = list(csv.DictReader(open(raw)))
    util = [r for r in filas if r['name'] != 'login' and float(r['t']) >= VENTANA_DESDE]
    ms = [float(r['ms']) for r in util]
    err = sum(int(r['error']) for r in util)
    t_max = max(float(r['t']) for r in util) if util else 0
    ventana = max(t_max - VENTANA_DESDE, 1)
    por = {}
    for r in util:
        por.setdefault(r['name'], []).append(float(r['ms']))
    cpu = [(float(a), float(b), float(c)) for a, b, c in (l.strip().split(',') for l in list(open(cpu_csv))[1:])]
    ini_abs = t_ini + 6
    cpu_v = [(b, c) for a, b, c in cpu if ini_abs + VENTANA_DESDE <= a <= t_fin]
    return {
        'config': config, 'mult': mult, 'usuarios': usuarios, 'peticiones': len(util), 'rps': round(len(util) / ventana, 1),
        'p50': round(pct(ms, 50)), 'p95': round(pct(ms, 95)), 'p99': round(pct(ms, 99)), 'max': round(max(ms)),
        'errores': err, 'cpu_proceso': round(statistics.mean(b for b, _ in cpu_v)) if cpu_v else None,
        'cpu_total': round(statistics.mean(c for _, c in cpu_v)) if cpu_v else None,
        'login_n': sum(1 for r in filas if r['name'] == 'login'),
        'por_endpoint': {k: {'n': len(v), 'p50': round(pct(v, 50)), 'p95': round(pct(v, 95))} for k, v in por.items()},
    }


if __name__ == '__main__':
    res = []
    for config in ('B', 'A'):
        for mult in (1, 2, 4):
            r = correr(config, mult)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            res.append(r)
            json.dump(res, open(os.path.join(AQUI, 'resultados.json'), 'w'), ensure_ascii=False, indent=1)
            time.sleep(5)
    print('FIN')
