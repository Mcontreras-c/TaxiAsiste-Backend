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

## Estado actual (actualizado 2026-08-22)
- Los 3 repos existen y estan funcionando de punta a punta:
  Backend (Django+Oracle), Frontend web (React+Vite+TS), Mobile (React Native+Expo)
- models.py, serializers.py y views.py de las 10 tablas ya estan escritos y probados
- La seccion "SQL del esquema" mas abajo sigue vigente como referencia de columnas y tipos
- FASE 1 (mapa de despacho, geocoding/rutas, polling, permisos por rol, Location Gate mobile)
  100% completada. FASE 2 en progreso — ver seccion "GPS, mapa del conductor y notificaciones"
  mas abajo para lo agregado despues de FASE 1

## GPS, mapa del conductor y notificaciones (FASE 2)
- Arquitectura de posicion: 100% REST + Polling, sin WebSockets/Channels (se probo y se
  descarto — respaldo en branch `dev-dortiiz-backup-*` del repo Mobile). Tabla
  UBICACION_ACTUAL (1:1 con MOVILES); `/api/ubicaciones/` filtra solo moviles que
  reportaron en los ultimos `SEGUNDOS_ONLINE=45` (moviles/views.py)
- Sesion unica por login: columna USUARIOS.sesion_actual + claim `sid` en el JWT — un
  login nuevo invalida el token de cualquier sesion anterior (401 "Sesion cerrada: se
  inicio sesion en otro dispositivo")
- Mobile — Conductor ahora tiene 4 tabs (antes 3): Fila Virtual, Solicitudes, Servicio
  Actual y **Mapa** (nueva, WebView + Leaflet/CARTO, mismo look que el mapa de Central;
  ve su propio movil centrado + otros moviles en linea, sin necesitar Google Maps API key)
- Mobile — rastreo en segundo plano: `expo-task-manager` + `startLocationUpdatesAsync`
  (foreground+background unificado), corre cada ~12s incluso con la app cerrada
  (foreground service de Android)
- Mobile — notificaciones: LOCALES unicamente (sin FCM/push remoto — no hay proyecto
  Firebase todavia). Se disparan desde la misma tarea de background de arriba: "te
  llamaron de la base", "viaje asignado" y "sesion cerrada en otro dispositivo". Si en
  el futuro se arma push remoto real, hace falta Firebase Cloud Messaging + credenciales
  en `eas credentials` (decision pendiente, no tomada)
- Mobile — boton EMERGENCIA: llama a Carabineros (133, antes tenia un bug que llamaba a
  Central). Se probo y DESCARTO una llamada 100% automatica via modulo nativo
  (`Intent.ACTION_CALL`): MIUI/Xiaomi (y probablemente otros fabricantes) la bloquean en
  silencio sin excepcion. Decision final: cuenta regresiva de 3s y despues abre el
  marcador (`Linking.openURL('tel:133')`), el conductor da el ultimo toque
- Frontend web — code-splitting: las paginas (menos Login) se cargan con `React.lazy` +
  `Suspense` en `App.tsx`. Bajó el chunk mas pesado de 1.28MB a ~380KB (Leaflet ya no
  se descarga si el usuario nunca visita Solicitudes/mapa)
- Pendiente real: push remoto (requiere Firebase), tests automatizados, CI,
  staging/produccion, mapa dentro de la app en tiempo real via push (hoy es polling)

## Roles del sistema (tabla ROLES)
- Administrador, Central, Tesorero, Conductor — manejados desde el Frontend web
- Paletero — SOLO existe en la app Mobile (no tiene pantallas en el frontend web).
  Ve la fila de base y puede llamar/retirar moviles. Usuario de prueba: paletero/paletero123
- Usuarios de prueba: admin/admin123, central/central123, tesorero/tesorero123,
  conductor/conductor123, paletero/paletero123

## Flujo operativo real del negocio (distinto al diseño original de abajo)
1. El pasajero puede llegar por 3 canales: TELEFONO (Central), APP, PRESENCIAL
2. La solicitud queda PENDIENTE y es visible para TODOS los conductores en la app mobile
3. Cualquier conductor puede "Aceptar solicitud" desde su celular → el sistema se la
   asigna a su movil (estado ASIGNADO) - primero que acepta, se la lleva
4. Si nadie la acepta desde la ruta, la Central puede verla en su panel web y asignarla
   manualmente a un movil especifico (mismo endpoint cambiar_estado, con `movil` en el body)
5. Conductor: ASIGNADO → EN_CURSO (inicia viaje) → COMPLETADO. Solo puede cancelar
   mientras esta ASIGNADO, no una vez EN_CURSO
6. Estados reales usados: PENDIENTE, ASIGNADO, EN_CURSO, COMPLETADO, CANCELADO
   (los estados ACEPTADO/REASIGNANDO del diseño original no se implementaron)

## Fila virtual y Paletero (real)
- El conductor entra/sale de la fila desde su propia app mobile (pestaña "Fila Virtual"),
  no hay un boton fisico "Llegada a base"
- La posicion se asigna automaticamente en el backend (perform_create de FilaBaseViewSet)
- El rol Paletero (mobile, pantalla separada del conductor) ve la fila ordenada por
  posicion y usa los botones Llamar (EN_ESPERA -> LLAMADO) y Retirar (-> RETIRADO)
- La Central en el frontend web tambien ve la fila (solo lectura, columna
  "Fila Virtual (Base)" en la pantalla de Solicitudes) para saber cuantos moviles
  hay en base como respaldo si ninguna solicitud pendiente es tomada por alguien en ruta

## Gotchas importantes para levantar el entorno
- Backend SIEMPRE con `python manage.py runserver 0.0.0.0:8000`, nunca sin el `0.0.0.0`
  (si no, solo escucha en localhost y el emulador/celular de la app mobile no puede conectar)
- Cuidado con lanzar el runserver dos veces (una manual + una de un agente/IA en background):
  quedan varios procesos python compitiendo por el puerto 8000 y confunde mucho al debuggear
- ALLOWED_HOSTS = ['*'] en settings.py (dev only, para permitir conexiones del emulador/celular)
- Windows suele bloquear los puertos 8000 (Django) y 8081 (Metro/Expo de la app mobile) por
  firewall la primera vez — ver detalles y guia completa en el README.md del repo Mobile

## Flujo operativo original de diseño (referencia historica, ya no vigente al 100%)
1. Pasajero llama a la central
2. Central busca pasajero por RUT (autocompletar)
3. Central registra solicitud (INMEDIATA o AGENDADA)
4. Sistema muestra móviles disponibles
5. Central asigna móvil → estado ASIGNADO
6. Conductor recibe notificación en app
7. Conductor acepta → ACEPTADO / rechaza → REASIGNANDO
8. Si acepta: EN_CURSO → COMPLETADO
9. Todo cambio queda en HISTORIAL_EVENTOS


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