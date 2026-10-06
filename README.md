# TaxiAsiste Backend

API REST en Django 6.x con PostgreSQL, JWT y documentacion Swagger.

## Requisitos

- Python 3.12+
- PostgreSQL 14+ (local o en el servidor)

## Configuracion rapida

```powershell
cd TaxiAsiste-Backend

# 1. Entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Variables de entorno
copy .env.example .env
# Editar .env: al menos SECRET_KEY, POSTGRES_PASSWORD y GOOGLE_MAPS_API_KEY

# 3. Base de datos (una sola vez, como usuario postgres)
psql -U postgres -h localhost -c "CREATE DATABASE taxiasiste_dev;"

# 4. Esquema de negocio: primero el base y luego los migrar_* (todos idempotentes)
foreach ($f in "create_business_schema_postgres","migrar_usuarios_nombre_apellido_postgres","migrar_usuarios_telefono_postgres","migrar_solicitudes_origen_latlng_postgres","migrar_reservas_postgres","migrar_fila_inactividad_llamado_postgres") {
  psql -U postgres -h localhost -d taxiasiste_dev -v ON_ERROR_STOP=1 -f "scripts/$f.sql"
}

# 5. Tablas internas de Django (auth, sessions, token_blacklist)
python manage.py migrate

# 6. Verificar
python manage.py check
python manage.py runserver 0.0.0.0:8000
```

**Importante:** siempre con `0.0.0.0:8000`, nunca `runserver` a secas — sin eso el
servidor solo escucha en `127.0.0.1` y ni el Frontend en otra red ni la app Mobile
(emulador o celular fisico) pueden conectarse. Ver mas gotchas de entorno en
`CONTEXTO.md`.

## Tests

```powershell
# Una sola vez por maquina (PostgreSQL local, usuario postgres):
psql -U postgres -h localhost -f scripts/setup_test_schema.sql
foreach ($f in "create_business_schema_postgres","migrar_usuarios_nombre_apellido_postgres","migrar_usuarios_telefono_postgres","migrar_solicitudes_origen_latlng_postgres","migrar_reservas_postgres","migrar_fila_inactividad_llamado_postgres") {
  psql -U postgres -h localhost -d taxiasiste_test -v ON_ERROR_STOP=1 -f "scripts/$f.sql"
}
$env:DJANGO_SETTINGS_MODULE="taxiasiste.settings_test"; python manage.py migrate

# Cada vez que quieras correr la suite:
pytest
```

Los tests corren contra una base PostgreSQL real y separada (`taxiasiste_test`) en
vez de contra un mock o sqlite: todos los modelos de negocio son `managed = False`
(el esquema se arma a mano con los scripts SQL de `scripts/`), asi que
`manage.py test`/migrations no crean esas tablas por si solas. `pytest.ini` +
`conftest.py` apuntan a esa base directamente, sin que Django intente crear ni
destruir nada en cada corrida. El `manage.py migrate` de arriba si hace falta una
vez, aparte: crea las tablas propias de Django que son managed=True (auth,
sessions y `token_blacklist` para el refresh JWT). Detalle en los comentarios de
`taxiasiste/settings_test.py`.

El orden de los scripts es el mismo que usa el CI (`.github/workflows/ci.yml`) y el
servidor de produccion; todos los `migrar_*` son idempotentes. Los scripts sin
sufijo `_postgres` (`create_business_schema.sql`, `upgrade_local_schema.sql`,
`add_sesion_unica.sql`, `setup_oracle_user.sql`) son del Oracle anterior y ya no se usan.


## Endpoints

| Ruta | Descripcion |
|------|-------------|
| `GET /api/ping/` | Health check (sin autenticacion) |
| `POST /api/token/` | Obtener token JWT |
| `POST /api/token/refresh/` | Renovar token |
| `GET /api/docs/` | Swagger UI |

## Base de datos

El motor es **PostgreSQL**. La conexion se configura con las variables `POSTGRES_*` del
`.env` (ver `.env.example`). Todos los modelos de negocio son `managed = False`: el esquema
se arma con los scripts SQL de `scripts/`, no con migrations de Django.

Historia: el proyecto partio sobre Oracle Database (ver el informe de la Unidad 1) y se migro a
PostgreSQL al pasar a produccion. Los scripts sin sufijo `_postgres` (`create_business_schema.sql`,
`upgrade_local_schema.sql`, `add_sesion_unica.sql`, `setup_oracle_user.sql`,
`_run_sql_script.py`) son de esa epoca y ya no se usan.
