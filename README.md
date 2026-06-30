# TaxiAsiste Backend

API REST en Django 6.x con Oracle, JWT y documentacion Swagger.

## Requisitos

- Python 3.12+ (probado con 3.14; usar Django 5.2+ o 6.x)
- Oracle Database (local o contenedor Docker `oracle-xe`)

## Configuracion rapida

```powershell
cd c:\TaxiAsiste_Backend

# 1. Entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Variables de entorno
copy .env.example .env
# Editar .env con tus credenciales

# 3. Usuario Oracle (solo la primera vez, con contenedor gvenzl/oracle-xe)
Get-Content scripts\setup_oracle_user.sql | docker exec -i oracle-xe sqlplus -s system/oracle@XEPDB1

# 4. Verificar
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
docker run -d --name oracle-xe -p 1521:1521 -e ORACLE_PASSWORD=oracle gvenzl/oracle-xe:21-slim
```

Credenciales por defecto del contenedor: `system/oracle` en el PDB `XEPDB1`.
