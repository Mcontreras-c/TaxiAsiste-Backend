# TaxiAsiste Backend

API REST en Django 6.x con Oracle, JWT y documentacion Swagger.

## Requisitos

- Python 3.12+ (probado con 3.14; usar Django 5.2+ o 6.x)
- Oracle Database (local o contenedor Docker `oracle-xe`)

## Configuracion rapida

```powershell
cd C:\Users\maira\OneDrive\Documentos\GitHub\TaxiAsiste-Backend

# 1. Entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Variables de entorno
copy .env.example .env
# Editar .env: ORACLE_PORT debe coincidir con el mapeo Docker (ej. 1523)

# 3. Usuario Oracle (solo la primera vez)
Get-Content scripts\setup_oracle_user.sql | docker exec -i oracle-xe_21slim sqlplus -s system/oracle@XEPDB1

# 4. Esquema de negocio (instalacion nueva o parche local)
Get-Content scripts\create_business_schema.sql | docker exec -i oracle-xe_21slim sqlplus -s taxiasiste_app/TaxiAsiste_App_2026@XEPDB1
# Si migraste desde otro PC y solo falta FILA_BASE:
Get-Content scripts\upgrade_local_schema.sql | docker exec -i oracle-xe_21slim sqlplus -s taxiasiste_app/TaxiAsiste_App_2026@XEPDB1

# 5. Tablas internas de Django
python manage.py migrate

# 6. Verificar
python manage.py check
python manage.py runserver
```

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
docker run -d --name oracle-xe_21slim -p 1523:1521 -p 5500:5500 -e ORACLE_PASSWORD=oracle gvenzl/oracle-xe:21-slim
```

En este equipo el contenedor activo es `oracle-xe_21slim` y Oracle escucha en el puerto host **1523**.

Credenciales por defecto del contenedor: `system/oracle` en el PDB `XEPDB1`.
