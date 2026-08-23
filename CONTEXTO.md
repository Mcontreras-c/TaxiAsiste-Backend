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
- Mobile — navegacion al punto de recogida/destino: la app NO intenta
  reemplazar la navegacion turn-by-turn (Waze/Google Maps ya lo hacen mejor
  y el conductor ya las conoce). En su lugar: (1) boton "Navegar" en
  Servicio Actual que abre Waze o Google Maps con la direccion en texto tal
  cual (sin geocoding propio, para no sumar un punto de falla a algo que el
  destino resuelve solo), y (2) en la pantalla Mapa, un pin + la ruta
  trazada (reusa `/api/geocodificar/` y `/api/ruta/`, los mismos que ya usa
  el Frontend web) desde la posicion del conductor hasta el punto relevante
  — solo informativo, se recalcula al cambiar de viaje/estado, no en cada
  tick del polling de posicion
- Mobile — Servicio Actual rediseñado, estilo apps de viajes (Uber/DiDi):
  mapa a pantalla completa de fondo (ruta al punto de recogida/destino,
  sin la flota completa — decluttered) con la tarjeta del pasajero y los
  botones de accion flotando encima, en vez de la lista de texto anterior.
  El mapa se extrajo a `components/MapaConRuta.tsx`, compartido con la
  pantalla Mapa (que sigue mostrando la flota completa via el prop
  `mostrarFlota`) para no duplicar la logica de WebView/polling/ruta
- Frontend web — code-splitting: las paginas (menos Login) se cargan con `React.lazy` +
  `Suspense` en `App.tsx`. Bajó el chunk mas pesado de 1.28MB a ~380KB (Leaflet ya no
  se descarga si el usuario nunca visita Solicitudes/mapa)
- Pendiente real: push remoto (requiere Firebase), CI, staging/produccion,
  mapa dentro de la app en tiempo real via push (hoy es polling)

## MOVILES.estado_operativo: EN_SERVICIO automatico
- El valor EN_SERVICIO existia en el modelo/DB desde el diseño original
  pero nunca se asignaba en ningun lado del codigo — era logica muerta
  (moviles_en_servicio en el dashboard siempre daba 0). Ahora
  `SolicitudViewSet.cambiar_estado` (solicitudes/views.py) lo conecta al
  ciclo de vida real de una solicitud:
  - PENDIENTE→ASIGNADO→**EN_CURSO**: el movil pasa a EN_SERVICIO (solo si
    estaba DISPONIBLE — no pisa un BLOQUEADO/INACTIVO puesto a mano)
  - EN_CURSO→COMPLETADO/CANCELADO: vuelve a DISPONIBLE (solo si el estado
    actual es justo EN_SERVICIO — no reactiva un movil que Central
    desconecto/bloqueo mientras el viaje seguia en curso)
  - Cancelar ANTES de EN_CURSO (desde ASIGNADO) no toca el movil: nunca
    paso a EN_SERVICIO, nada que revertir
  - El mapa de Central ya pintaba EN_SERVICIO de azul (COLOR_ESTADO en
    MapaDespacho.tsx) — cero cambios de Frontend, el color cambia solo en
    el proximo poll de /api/moviles/ (cada 5s) apenas el backend lo marca
  - Cubierto con 5 tests nuevos en test_transiciones.py contra Oracle real,
    mas verificado a mano contra el backend de desarrollo (DISPONIBLE ->
    EN_SERVICIO -> DISPONIBLE via curl, ciclo completo)

## Tests automatizados (Backend)
- pytest + pytest-django, contra un esquema Oracle real y separado
  (`taxiasiste_test`, mismo contenedor Docker) — NO contra sqlite ni mocks.
  Necesario porque managed=False en todos los modelos hace que
  `manage.py test`/migrations no puedan crear las tablas de negocio por si
  solos. Ver seccion "Tests" del README del Backend para el setup una vez
  por maquina y `taxiasiste/settings_test.py` para el detalle tecnico
- Cobertura inicial: login + sesion unica, transiciones de estado de
  SOLICITUDES, fila virtual (posicion automatica, anti-duplicado, llamar/
  retirar), permisos de MOVILES por rol, filtro de 45s de UBICACION_ACTUAL
- **Bug real encontrado y arreglado al escribir estos tests**: todas las PK
  son FloatField (Oracle NUMBER sin escala fija) y se serializan en JSON
  como `4.0`, no `4`. El router de DRF por defecto excluye el punto de la
  URL de un recurso (para distinguirlo de un sufijo `.json`), asi que
  cualquier accion de detalle armada con un ID que vino de una respuesta
  JSON previa (el caso normal, ej. `salirDeFila()` en el Mobile) devolvia
  404 en vez de encontrar el registro. Se agrego
  `taxiasiste/utils/routers.py` (`DecimalPkRouter`) usado ahora en los 5
  `urls.py` de la app — antes de este fix, "Salir de la fila" y los botones
  Llamar/Retirar del Paletero estaban rotos en produccion

## JWT: refresh automatico (Frontend + Mobile)
- Ya no dependen solo de que el access token (8h) siga vigente: ambos
  clientes axios ahora interceptan un 401, llaman a `/api/token/refresh/`
  con el refresh token guardado (1 dia de vida), y reintentan la request
  original una sola vez con el access token nuevo — sin backend nuevo,
  simplejwt ya copia el claim `sid` del refresh al access nuevo (verificado
  con curl contra el backend real: mismo `sid`, endpoint protegido responde
  200 con el token refrescado)
- Requests concurrentes que pisan un 401 al mismo tiempo (pollers en
  paralelo) comparten una sola promesa de refresh en vuelo, no disparan
  `/token/refresh/` por triplicado
- Si el refresh token tambien esta vencido/invalido (o es la sesion-unica
  la que lo rechaza), NO reintenta en loop — cae al logout normal
  (`useAuthStore.logout()` en Frontend, `onSessionExpired()` en Mobile)
- Cubierto con tests (`src/api/client.test.ts` en ambos repos) usando
  `axios-mock-adapter`: refresh+reintento exitoso, sin refresh_token
  guardado, refresh token invalido, y dedupe de refresh concurrente
- Frontend y Mobile YA tienen tests automatizados (Vitest+RTL / Jest+jest-expo)
  y CI en los 3 repos (GitHub Actions, verificado corriendo en verde)

## JWT: blacklist + logout real (SIN rotacion — ver incidente abajo)
- `rest_framework_simplejwt.token_blacklist` instalado y migrado (esquemas
  dev y test)
- Nuevo endpoint `POST /api/logout/` (`{refresh}` -> invalida ese token de
  inmediato): antes un logout solo borraba el token del dispositivo, el
  refresh seguia siendo valido en el backend hasta por 1 dia. Frontend y
  Mobile lo llaman best-effort (fire-and-forget) al cerrar sesion, sin
  bloquear el logout local si falla la red
- Cubierto con tests: `taxiasiste/test_blacklist.py` (backend, 5 tests
  contra Oracle real) + `src/api/auth.test.ts` (Frontend, 3 tests del
  logout best-effort) + mocks en `client.test.ts` de ambos repos

### INCIDENTE — ROTATE_REFRESH_TOKENS probado y descartado (2026-08-23)
Se activo brevemente `SIMPLE_JWT.ROTATE_REFRESH_TOKENS` +
`BLACKLIST_AFTER_ROTATION` (cada refresh consume el token usado y entrega
uno nuevo). **Causo una regresion real en produccion**: el GPS del
conductor dejaba de actualizarse "despues de un rato", tanto en el mapa
web de Central como en el propio celular del conductor — solo un
logout+login lo arreglaba.

Causa raiz: la app Mobile tiene varios pollers concurrentes que comparten
el mismo refresh token guardado (fila-base, solicitudes, notificaciones,
la tarea de ubicacion en background). Cuando el access token de 8h vence,
todos pueden pisar un 401 casi al mismo tiempo. El interceptor de axios
dedupea refrescos concurrentes DENTRO de un mismo contexto JS, pero la
tarea de ubicacion en background puede correr en un contexto headless
separado del de la app en primer plano (TaskManager en Android) — dos
refrescos casi simultaneos desde contextos distintos podian leer el MISMO
refresh token de AsyncStorage antes de que ninguno terminara de escribir
el nuevo. El backend, con rotacion activada, invalida (blacklist) el
token usado en cuanto el primero lo consume — el segundo intento, con ese
mismo token ya en blacklist, fallaba con 401 de forma permanente hasta el
proximo login manual, matando ese poller (incluido el de ubicacion) en
silencio.

Se revirtio: el refresh token vuelve a ser reusable durante toda su vida
util (1 dia), sin rotacion. El blacklist en si se mantiene activo (sigue
siendo util) pero solo se dispara en el logout explicito — una accion
unica y deliberada, sin la concurrencia que causaba la carrera. Frontend
y Mobile: `refreshToken()`/`refrescarToken()` ahora guardan el campo
`refresh` de la respuesta solo si viene presente (defensivo, no rompe si
se revierte esta decision mas adelante). Tests actualizados para reflejar
reuso permitido en vez de rotacion.

## PENDIENTE — a consultar con el grupo
- **Falta el script SQL de TESORERIA_MOVIMIENTOS**: la tabla (y su secuencia
  seq_tesoreria_mov) usada por TesoreriaMovimiento (socios/models.py) existe
  en la base de datos de desarrollo y las pantallas Tesoreria/TesoreriaAdmin
  del Frontend ya funcionan contra ella, pero NINGUN script versionado la
  crea (ni create_business_schema.sql ni upgrade_local_schema.sql) — solo
  aparece referenciada en reset_datos_prueba.sql y verificar_datos.sql. Esto
  salio a la luz al armar desde cero el esquema Oracle de test
  (taxiasiste_test) siguiendo exactamente los scripts documentados: la tabla
  simplemente no aparece. Cualquiera que instale el proyecto de cero (o
  levante Oracle en otra maquina) se va a quedar sin Tesoreria funcionando.
  Falta decidir en equipo: escribir el script faltante (documentando la
  definicion real que ya existe en dev) y quien se encarga

- **HISTORIAL_EVENTOS nunca se escribe**: la tabla, el modelo, el
  serializer y el endpoint de solo lectura (`/api/historial/`) existen,
  pero no hay un solo `.objects.create()` de HistorialEvento en ningun
  view del proyecto — es una tabla de auditoria que hoy esta siempre
  vacia. Hay que decidir: implementar el registro real (que accion en
  moviles/solicitudes/fila-base/etc. dispara que evento) o sacar el
  endpoint hasta que se implemente, para no ofrecer una funcionalidad que
  no hace nada

- **Sin paginacion en DRF**: ningun endpoint pagina resultados — hoy no se
  nota porque los datos de prueba son pocos, pero escala mal apenas haya
  meses de SOLICITUDES/HISTORIAL_EVENTOS reales en produccion

- **`bloquear_morosos` sin scheduler**: el management command que bloquea
  socios con cuota vencida existe (`socios/management/commands/`) pero nada
  lo dispara automaticamente — hoy hay que correrlo a mano. Necesita un
  cron/Celery beat, probablemente como parte de la conversacion de
  staging/produccion

- **Sin logging/monitoreo de errores en backend**: no hay Sentry ni logging
  estructurado — un 500 en produccion hoy solo se ve si alguien esta
  mirando la consola del server en el momento en que pasa

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