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
# Una sola vez por maquina/instancia de Oracle:
Get-Content scripts\setup_test_schema.sql | docker exec -i oracle-xe sqlplus -s system/oracle@XEPDB1
$env:ORACLE_USER="taxiasiste_test"; $env:ORACLE_PASSWORD="TaxiAsiste_Test_2026"
python scripts\_run_sql_script.py scripts\create_business_schema.sql
python scripts\_run_sql_script.py scripts\upgrade_local_schema.sql
python scripts\_run_sql_script.py scripts\add_sesion_unica.sql

# Cada vez que quieras correr la suite:
pytest
```

Los tests corren contra un esquema Oracle real y separado (`taxiasiste_test`,
mismo contenedor Docker) en vez de contra un mock o una base sqlite — todos
los modelos son `managed = False` (ver seccion Oracle mas abajo), asi que
`manage.py test`/migrations no sirven para crear las tablas de negocio.
`pytest.ini` + `conftest.py` apuntan a este esquema directamente sin que
Django intente crear ni destruir nada en cada corrida. Detalle completo en
los comentarios de `taxiasiste/settings_test.py`.

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
