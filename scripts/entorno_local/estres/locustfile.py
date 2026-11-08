"""Escenario de la prueba de estres de TaxiAsiste.
 - Conductor: reporta su GPS cada 12 s (POST /api/ubicaciones/mia/)
 - CentralMapa: consulta el mapa cada 4 s (GET /api/ubicaciones/)
 - CentralFila: consulta la fila cada 3 s (GET /api/fila-base/)
Cada usuario virtual usa una cuenta propia (sesion unica por usuario)."""
import csv
import itertools
import os
import random
import time

from locust import HttpUser, constant, events, task

PW = 'Stress2026!'
SALIDA = os.environ.get('STRESS_RAW', 'raw.csv')
T0 = {'t': None}
FILAS = []
cond = itertools.count(1)
mapa = itertools.count(1)
fila = itertools.count(1)


@events.test_start.add_listener
def inicio(environment, **kw):
    T0['t'] = time.time()


@events.request.add_listener
def registro(request_type, name, response_time, response_length, exception, **kw):
    FILAS.append((round(time.time() - T0['t'], 2), name, round(response_time, 1), 1 if exception else 0))


@events.quitting.add_listener
def fin(environment, **kw):
    with open(SALIDA, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['t', 'name', 'ms', 'error'])
        w.writerows(FILAS)


class Base(HttpUser):
    abstract = True
    host = 'http://127.0.0.1:8765'

    def entrar(self, usuario):
        r = self.client.post('/api/login/', json={'username': usuario, 'password': PW}, name='login')
        if r.status_code == 200:
            tok = r.json().get('access') or r.json().get('token')
            self.client.headers['Authorization'] = f'Bearer {tok}'
            return True
        return False


class Conductor(Base):
    weight = 100
    wait_time = constant(12)

    def on_start(self):
        self.n = next(cond)
        self.ok = self.entrar(f'stress_cond{self.n:03d}')
        time.sleep(random.uniform(0, 12))   # desfasar a los conductores

    @task
    def gps(self):
        if self.ok:
            self.client.post('/api/ubicaciones/mia/', json={'lat': -33.40 + random.random() / 50, 'lng': -70.60 + random.random() / 50},
                             name='GPS conductor')


class CentralMapa(Base):
    weight = 5
    wait_time = constant(4)

    def on_start(self):
        self.n = next(mapa)
        self.ok = self.entrar(f'stress_central{self.n:03d}')
        time.sleep(random.uniform(0, 4))

    @task
    def mapa(self):
        if self.ok:
            self.client.get('/api/ubicaciones/', name='Mapa de Central')


class CentralFila(Base):
    weight = 20
    wait_time = constant(3)

    def on_start(self):
        self.n = 20 + next(fila)
        self.ok = self.entrar(f'stress_central{self.n:03d}')
        time.sleep(random.uniform(0, 3))

    @task
    def ver_fila(self):
        if self.ok:
            self.client.get('/api/fila-base/', name='Fila virtual')
