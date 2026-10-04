# TaxiAsiste Backend

API REST en Django 6.x con Oracle, JWT y documentacion Swagger.

## Requisitos

- Python 3.12+ (probado con 3.14; usar Django 5.2+ o 6.x)
- Oracle Database (local o contenedor Docker `oracle-xe`)

## Configuracion rapida

```powershell
cd TaxiAsiste-Backend

# 1. Entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Variables de entorno
copy .env.example .env
# Editar .env: ORACLE_PORT debe coincidir con el mapeo Docker (ej. 1523)

# 3. Usuario Oracle (solo la primera vez)
Get-Content scripts\setup_oracle_user.sql | docker exec -i oracle-xe sqlplus -s system/oracle@XEPDB1

# 4. Esquema de negocio (instalacion nueva o parche local)
Get-Content scripts\create_business_schema.sql | docker exec -i oracle-xe sqlplus -s taxiasiste_app/TaxiAsiste_App_2026@XEPDB1
# Si migraste desde otro PC y solo falta FILA_BASE:
Get-Content scripts\upgrade_local_schema.sql | docker exec -i oracle-xe sqlplus -s taxiasiste_app/TaxiAsiste_App_2026@XEPDB1

# 5. Tablas internas de Django
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

> **Nota:** el resto de este README (instalacion y seccion "Oracle") quedo de la
> epoca de Oracle y esta desactualizado; la base actual es PostgreSQL (ver `.env`).

## Endpoints

| Ruta | Descripcion |
|------|-------------|
| `GET /api/ping/` | Health check (sin autenticacion) |
| `POST /api/token/` | Obtener token JWT |
| `POST /api/token/refresh/` | Renovar token |
| `GET /api/docs/` | Swagger UI |

## Oracle

El proyecto soporta dos modos de conexion via `.env`:

- **Service name** (Docker XE): define `ORACLE_SERVICE_NAME=XEPDB1`
- **SID clasico** (escritorio): deja `ORACLE_SERVICE_NAME` vacio y usa `ORACLE_SID=TAXIDB`

Contenedor Docker usado en este equipo:

```powershell
docker run -d --name oracle-xe -p 1523:1521 -p 5500:5500 -e ORACLE_PASSWORD=oracle gvenzl/oracle-xe:21-slim
```

En este equipo el contenedor activo es `oracle-xe` y Oracle escucha en el puerto host **1523**.

Credenciales por defecto del contenedor: `system/oracle` en el PDB `XEPDB1`.
