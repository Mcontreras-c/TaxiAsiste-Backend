-- Esquema completo TaxiAsiste (12 tablas + secuencias) -- version PostgreSQL
-- Ejecutar contra la base taxiasiste_dev (ver POSTGRES_* en .env)
--
-- IMPORTANTE: los nombres de tabla van entre comillas dobles para preservar
-- las mayusculas (Meta.db_table en los modelos Django usa 'USUARIOS', no
-- 'usuarios') -- sin comillas, Postgres pliega todo a minuscula y Django
-- ya no encuentra la tabla ("no existe la relacion").

-- Secuencias
CREATE SEQUENCE seq_roles START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE seq_usuarios START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE seq_socios START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE seq_cuotas START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE seq_bloqueos START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE seq_moviles START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE seq_fila_base START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE seq_pasajeros START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE seq_solicitudes START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE seq_historial START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE seq_ubicaciones START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE seq_tesoreria_mov START WITH 1 INCREMENT BY 1;

-- ROLES
CREATE TABLE "ROLES" (
    id_rol INTEGER PRIMARY KEY,
    nombre_rol VARCHAR(30) UNIQUE NOT NULL,
    descripcion VARCHAR(200),
    activo SMALLINT DEFAULT 1
);

-- USUARIOS
CREATE TABLE "USUARIOS" (
    id_usuario INTEGER PRIMARY KEY,
    id_rol INTEGER NOT NULL REFERENCES "ROLES"(id_rol),
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE,
    estado VARCHAR(20) DEFAULT 'ACTIVO',
    fecha_creacion DATE DEFAULT CURRENT_DATE,
    ultimo_acceso TIMESTAMP,
    sesion_actual VARCHAR(64)
);

-- SOCIOS
CREATE TABLE "SOCIOS" (
    id_socio INTEGER PRIMARY KEY,
    id_usuario INTEGER UNIQUE REFERENCES "USUARIOS"(id_usuario),
    rut VARCHAR(12) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    telefono VARCHAR(20),
    direccion VARCHAR(200),
    estado_socio VARCHAR(20) DEFAULT 'ACTIVO',
    fecha_ingreso DATE DEFAULT CURRENT_DATE,
    fecha_egreso DATE
);

-- CUOTAS
CREATE TABLE "CUOTAS" (
    id_cuota INTEGER PRIMARY KEY,
    id_socio INTEGER NOT NULL REFERENCES "SOCIOS"(id_socio),
    periodo DATE NOT NULL,
    monto NUMERIC(10,2) NOT NULL,
    estado_pago VARCHAR(20) DEFAULT 'PENDIENTE',
    fecha_vencimiento DATE NOT NULL,
    fecha_pago DATE,
    observacion VARCHAR(300),
    CONSTRAINT uq_cuota_socio_periodo UNIQUE (id_socio, periodo)
);

-- BLOQUEOS
CREATE TABLE "BLOQUEOS" (
    id_bloqueo INTEGER PRIMARY KEY,
    id_socio INTEGER NOT NULL REFERENCES "SOCIOS"(id_socio),
    id_usuario_registra INTEGER REFERENCES "USUARIOS"(id_usuario),
    motivo VARCHAR(200) NOT NULL,
    tipo_bloqueo VARCHAR(30) DEFAULT 'CUOTA_VENCIDA',
    fecha_inicio DATE DEFAULT CURRENT_DATE,
    fecha_fin DATE,
    activo SMALLINT DEFAULT 1
);

-- TESORERIA_MOVIMIENTOS
CREATE TABLE "TESORERIA_MOVIMIENTOS" (
    id_movimiento INTEGER PRIMARY KEY,
    id_usuario_registra INTEGER REFERENCES "USUARIOS"(id_usuario),
    id_cuota INTEGER REFERENCES "CUOTAS"(id_cuota),
    tipo VARCHAR(10) NOT NULL,
    categoria VARCHAR(30) NOT NULL,
    descripcion VARCHAR(300) NOT NULL,
    monto NUMERIC(10,2) NOT NULL,
    fecha DATE NOT NULL,
    CONSTRAINT chk_tesoreria_tipo CHECK (tipo IN ('INGRESO','EGRESO')),
    CONSTRAINT chk_tesoreria_categoria CHECK (categoria IN ('CUOTA','MULTA','GASTO_OPERACIONAL','OTRO'))
);

-- MOVILES
CREATE TABLE "MOVILES" (
    id_movil INTEGER PRIMARY KEY,
    id_socio INTEGER NOT NULL REFERENCES "SOCIOS"(id_socio),
    patente VARCHAR(10) UNIQUE NOT NULL,
    marca VARCHAR(50),
    modelo VARCHAR(50),
    anio SMALLINT,
    color VARCHAR(30),
    estado_operativo VARCHAR(20) DEFAULT 'DISPONIBLE',
    fecha_registro DATE DEFAULT CURRENT_DATE
);

-- FILA_BASE
CREATE TABLE "FILA_BASE" (
    id_fila INTEGER PRIMARY KEY,
    id_movil INTEGER NOT NULL REFERENCES "MOVILES"(id_movil),
    posicion INTEGER NOT NULL,
    fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_llamado TIMESTAMP,
    fecha_salida TIMESTAMP,
    estado VARCHAR(20) DEFAULT 'EN_ESPERA',
    CONSTRAINT chk_fila_estado CHECK (estado IN ('EN_ESPERA','LLAMADO','RETIRADO'))
);

-- UBICACION_ACTUAL
CREATE TABLE "UBICACION_ACTUAL" (
    id_ubicacion INTEGER PRIMARY KEY,
    id_movil INTEGER UNIQUE NOT NULL REFERENCES "MOVILES"(id_movil),
    lat NUMERIC(10,6) NOT NULL,
    lng NUMERIC(10,6) NOT NULL,
    heading NUMERIC(5,1),
    velocidad_kmh NUMERIC(5,1),
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_ubicacion_lat CHECK (lat BETWEEN -90 AND 90),
    CONSTRAINT chk_ubicacion_lng CHECK (lng BETWEEN -180 AND 180)
);

-- PASAJEROS
CREATE TABLE "PASAJEROS" (
    id_pasajero INTEGER PRIMARY KEY,
    rut VARCHAR(12) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    telefono VARCHAR(20),
    direccion_frecuente VARCHAR(200),
    fecha_registro DATE DEFAULT CURRENT_DATE,
    activo SMALLINT DEFAULT 1
);

-- SOLICITUDES
CREATE TABLE "SOLICITUDES" (
    id_solicitud INTEGER PRIMARY KEY,
    id_pasajero INTEGER REFERENCES "PASAJEROS"(id_pasajero),
    id_movil INTEGER REFERENCES "MOVILES"(id_movil),
    id_usuario_central INTEGER REFERENCES "USUARIOS"(id_usuario),
    folio VARCHAR(20) UNIQUE NOT NULL,
    origen VARCHAR(200) NOT NULL,
    origen_lat NUMERIC(10, 6),
    origen_lng NUMERIC(10, 6),
    destino VARCHAR(200) NOT NULL,
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(20) DEFAULT 'PENDIENTE',
    canal_entrada VARCHAR(20) DEFAULT 'TELEFONO',
    observaciones VARCHAR(500),
    fecha_asignacion TIMESTAMP,
    fecha_inicio TIMESTAMP,
    fecha_termino TIMESTAMP
);

-- HISTORIAL_EVENTOS
CREATE TABLE "HISTORIAL_EVENTOS" (
    id_evento INTEGER PRIMARY KEY,
    id_usuario INTEGER REFERENCES "USUARIOS"(id_usuario),
    entidad_tipo VARCHAR(30) NOT NULL,
    entidad_id INTEGER NOT NULL,
    evento VARCHAR(100) NOT NULL,
    estado_anterior VARCHAR(50),
    estado_nuevo VARCHAR(50),
    detalle VARCHAR(500),
    ip_origen VARCHAR(45),
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_hist_entidad CHECK (entidad_tipo IN (
        'SOLICITUD','BLOQUEO','CUOTA','MOVIL','SOCIO','USUARIO','PASAJERO','FILA_BASE'
    ))
);
