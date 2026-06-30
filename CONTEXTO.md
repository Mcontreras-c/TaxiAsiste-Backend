# Contexto del proyecto TaxiAsiste

## Stack
- Django 5.1 + Django REST Framework 3.15
- Oracle 21c XE Slim en Docker (contenedor: oracle-xe)
- Python 3.12 en venv
- JWT con djangorestframework-simplejwt
- Swagger con drf-spectacular

## Base de datos
- Usuario Oracle: taxiasiste_app
- Servicio: XEPDB1, puerto 1521
- 9 tablas de negocio ya creadas con SQL directo
- managed = False en todos los modelos (Django no gestiona el esquema)
- Las secuencias Oracle se llaman seq_roles, seq_usuarios, etc.

## Apps Django
- taxiasiste/usuarios/   → modelos: Roles, Usuarios
- taxiasiste/socios/     → modelos: Socios, Cuotas, Bloqueos
- taxiasiste/moviles/    → modelos: Moviles
- taxiasiste/solicitudes/→ modelos: Pasajeros, Solicitudes
- taxiasiste/reportes/   → modelos: HistorialEventos

## Decisiones de arquitectura
- Toda la lógica de negocio vive en Django (services/signals)
- Oracle solo tiene estructura, constraints e integridad referencial
- Sin triggers ni stored procedures en Oracle
- Bloqueo automático por cuota vencida: management command diario en Django
- PASAJEROS permite autocompletar por RUT en la central (no es marketing)

## Estado actual
- migrate ejecutado correctamente
- Tablas de negocio creadas en Oracle
- models.py distribuidos en cada app (managed=False)
- Próximo paso: serializers y views por app