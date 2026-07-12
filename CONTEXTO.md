# TaxiAsiste — Contexto del proyecto

## Stack
- Django 5.1 + Django REST Framework 3.15
- Oracle 21c XE Slim en Docker (contenedor: oracle-xe)
- Python 3.12 en venv
- JWT con djangorestframework-simplejwt
- Swagger con drf-spectacular

## Base de datos Oracle
- Usuario: taxiasiste_app / TaxiAsiste_App_2026
- Servicio: XEPDB1, puerto 1521
- 10 tablas de negocio creadas con SQL directo (NO con migrations)
- managed = False en todos los modelos Django
- Secuencias: seq_roles, seq_usuarios, seq_socios, seq_cuotas,
  seq_bloqueos, seq_moviles, seq_fila_base, seq_pasajeros,
  seq_solicitudes, seq_historial

## Las 10 tablas y su distribución por app

### App: usuarios/
- ROLES — roles del sistema (Administrador, Central, Tesorero, Conductor)
- USUARIOS — personas con acceso al sistema

### App: socios/ (dentro de taxiasiste/)
- SOCIOS — conductores del sindicato (pueden existir sin login)
- CUOTAS — cuotas mensuales, gestionadas por el Tesorero
- BLOQUEOS — bloqueos por cuota vencida u otro motivo

### App: moviles/
- MOVILES — vehículos del sindicato, uno por socio
- FILA_BASE — cola ordenada de móviles en base esperando
  ser llamados por el paletero (orden por llegada)

### App: solicitudes/
- PASAJEROS — registro frecuente, autocompletar por RUT
- SOLICITUDES — solicitudes de servicio (INMEDIATA o AGENDADA)

### App: reportes/
- HISTORIAL_EVENTOS — trazabilidad genérica polimórfica

## Decisiones de arquitectura clave
- Toda la lógica de negocio vive en Django, no en Oracle
- Sin triggers ni stored procedures en Oracle
- Bloqueo automático por cuota vencida: management command diario
- FILA_BASE: posición asignada por Django al presionar
  "Llegada a base" en la app — el paletero ve la cola ordenada
- SOLICITUDES tiene tipo_solicitud (INMEDIATA/AGENDADA),
  intentos_asignacion y motivo_cancelacion
- Estados de SOLICITUDES: PENDIENTE → ASIGNADO → ACEPTADO
  → EN_CURSO → COMPLETADO / CANCELADO / REASIGNANDO

## Estado actual
- migrate ejecutado correctamente (tablas Django en Oracle)
- 10 tablas de negocio creadas y verificadas en DBeaver
- models.py de cada app probablemente desactualizados
  (tienen las 9 tablas viejas, falta FILA_BASE y campos nuevos)
- Próximo paso: reescribir models.py de cada app con las
  10 tablas actuales y luego crear serializers y views

## Flujo operativo del negocio
1. Pasajero llama a la central
2. Central busca pasajero por RUT (autocompletar)
3. Central registra solicitud (INMEDIATA o AGENDADA)
4. Sistema muestra móviles disponibles
5. Central asigna móvil → estado ASIGNADO
6. Conductor recibe notificación en app
7. Conductor acepta → ACEPTADO / rechaza → REASIGNANDO
8. Si acepta: EN_CURSO → COMPLETADO
9. Todo cambio queda en HISTORIAL_EVENTOS

## Fila virtual (paletero)
- Conductor llega a base y presiona botón en app
- Django asigna posición según orden de llegada
- Paletero ve lista ordenada en tiempo real
- Paletero llama al primero → estado LLAMADO
- Móvil sale → estado RETIRADO


## SQL del esquema (referencia exacta de columnas y tipos)

### ROLES
id_rol NUMBER PK, nombre_rol VARCHAR2(30) UNIQUE NOT NULL,
descripcion VARCHAR2(200), activo NUMBER(1) DEFAULT 1

### USUARIOS
id_usuario NUMBER PK, id_rol NUMBER FK→ROLES,
username VARCHAR2(50) UNIQUE, password_hash VARCHAR2(255),
email VARCHAR2(100) UNIQUE, estado VARCHAR2(20) DEFAULT 'ACTIVO',
fecha_creacion DATE DEFAULT SYSDATE, ultimo_acceso TIMESTAMP

### SOCIOS
id_socio NUMBER PK, id_usuario NUMBER FK→USUARIOS (opcional, UNIQUE),
rut VARCHAR2(12) UNIQUE, nombre VARCHAR2(100), apellido VARCHAR2(100),
telefono VARCHAR2(20), direccion VARCHAR2(200),
estado_socio VARCHAR2(20) DEFAULT 'ACTIVO',
fecha_ingreso DATE DEFAULT SYSDATE, fecha_egreso DATE

### CUOTAS
id_cuota NUMBER PK, id_socio NUMBER FK→SOCIOS,
periodo DATE, monto NUMBER(10,2), estado_pago VARCHAR2(20) DEFAULT 'PENDIENTE',
fecha_vencimiento DATE, fecha_pago DATE, observacion VARCHAR2(300)
UNIQUE(id_socio, periodo)

### BLOQUEOS
id_bloqueo NUMBER PK, id_socio NUMBER FK→SOCIOS,
id_usuario_registra NUMBER FK→USUARIOS (opcional),
motivo VARCHAR2(200), tipo_bloqueo VARCHAR2(30) DEFAULT 'CUOTA_VENCIDA',
fecha_inicio DATE DEFAULT SYSDATE, fecha_fin DATE,
activo NUMBER(1) DEFAULT 1

### MOVILES
id_movil NUMBER PK, id_socio NUMBER FK→SOCIOS,
patente VARCHAR2(10) UNIQUE, marca VARCHAR2(50), modelo VARCHAR2(50),
anio NUMBER(4), color VARCHAR2(30),
estado_operativo VARCHAR2(20) DEFAULT 'DISPONIBLE',
fecha_registro DATE DEFAULT SYSDATE

### FILA_BASE
id_fila NUMBER PK, id_movil NUMBER FK→MOVILES,
posicion NUMBER NOT NULL, fecha_ingreso TIMESTAMP DEFAULT SYSTIMESTAMP,
fecha_llamado TIMESTAMP, fecha_salida TIMESTAMP,
estado VARCHAR2(20) DEFAULT 'EN_ESPERA'
CHECK estado IN ('EN_ESPERA','LLAMADO','RETIRADO')

### PASAJEROS
id_pasajero NUMBER PK, rut VARCHAR2(12) UNIQUE,
nombre VARCHAR2(100), apellido VARCHAR2(100),
telefono VARCHAR2(20), direccion_frecuente VARCHAR2(200),
fecha_registro DATE DEFAULT SYSDATE, activo NUMBER(1) DEFAULT 1

### SOLICITUDES
id_solicitud NUMBER PK, id_pasajero NUMBER FK→PASAJEROS (opcional),
id_movil NUMBER FK→MOVILES (opcional),
id_usuario_central NUMBER FK→USUARIOS (opcional),
folio VARCHAR2(20) UNIQUE, tipo_solicitud VARCHAR2(20) DEFAULT 'INMEDIATA',
origen VARCHAR2(200), destino VARCHAR2(200),
fecha_hora_registro TIMESTAMP DEFAULT SYSTIMESTAMP,
fecha_programada TIMESTAMP,
estado VARCHAR2(20) DEFAULT 'PENDIENTE',
canal_entrada VARCHAR2(20) DEFAULT 'TELEFONO',
intentos_asignacion NUMBER DEFAULT 0,
observaciones VARCHAR2(500), fecha_asignacion TIMESTAMP,
fecha_inicio TIMESTAMP, fecha_termino TIMESTAMP,
motivo_cancelacion VARCHAR2(300)
CHECK tipo_solicitud IN ('INMEDIATA','AGENDADA')
CHECK estado IN ('PENDIENTE','ASIGNADO','ACEPTADO','REASIGNANDO',
                 'EN_CURSO','COMPLETADO','CANCELADO')

### HISTORIAL_EVENTOS
id_evento NUMBER PK, id_usuario NUMBER FK→USUARIOS (opcional),
entidad_tipo VARCHAR2(30), entidad_id NUMBER,
evento VARCHAR2(100), estado_anterior VARCHAR2(50),
estado_nuevo VARCHAR2(50), detalle VARCHAR2(500),
ip_origen VARCHAR2(45), fecha_hora TIMESTAMP DEFAULT SYSTIMESTAMP
CHECK entidad_tipo IN ('SOLICITUD','BLOQUEO','CUOTA','MOVIL',
                       'SOCIO','USUARIO','PASAJERO','FILA_BASE')