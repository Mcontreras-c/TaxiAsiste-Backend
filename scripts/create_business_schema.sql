-- Esquema completo TaxiAsiste (10 tablas + secuencias)
-- Ejecutar como taxiasiste_app en XEPDB1

-- Secuencias
CREATE SEQUENCE seq_roles START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_usuarios START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_socios START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_cuotas START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_bloqueos START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_moviles START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_fila_base START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_pasajeros START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_solicitudes START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_historial START WITH 1 INCREMENT BY 1 NOCACHE;

-- ROLES
CREATE TABLE ROLES (
    id_rol NUMBER PRIMARY KEY,
    nombre_rol VARCHAR2(30) UNIQUE NOT NULL,
    descripcion VARCHAR2(200),
    activo NUMBER(1) DEFAULT 1
);

-- USUARIOS
CREATE TABLE USUARIOS (
    id_usuario NUMBER PRIMARY KEY,
    id_rol NUMBER NOT NULL REFERENCES ROLES(id_rol),
    username VARCHAR2(50) UNIQUE NOT NULL,
    password_hash VARCHAR2(255) NOT NULL,
    email VARCHAR2(100) UNIQUE,
    estado VARCHAR2(20) DEFAULT 'ACTIVO',
    fecha_creacion DATE DEFAULT SYSDATE,
    ultimo_acceso TIMESTAMP
);

-- SOCIOS
CREATE TABLE SOCIOS (
    id_socio NUMBER PRIMARY KEY,
    id_usuario NUMBER UNIQUE REFERENCES USUARIOS(id_usuario),
    rut VARCHAR2(12) UNIQUE NOT NULL,
    nombre VARCHAR2(100) NOT NULL,
    apellido VARCHAR2(100) NOT NULL,
    telefono VARCHAR2(20),
    direccion VARCHAR2(200),
    estado_socio VARCHAR2(20) DEFAULT 'ACTIVO',
    fecha_ingreso DATE DEFAULT SYSDATE,
    fecha_egreso DATE
);

-- CUOTAS
CREATE TABLE CUOTAS (
    id_cuota NUMBER PRIMARY KEY,
    id_socio NUMBER NOT NULL REFERENCES SOCIOS(id_socio),
    periodo DATE NOT NULL,
    monto NUMBER(10,2) NOT NULL,
    estado_pago VARCHAR2(20) DEFAULT 'PENDIENTE',
    fecha_vencimiento DATE NOT NULL,
    fecha_pago DATE,
    observacion VARCHAR2(300),
    CONSTRAINT uq_cuota_socio_periodo UNIQUE (id_socio, periodo)
);

-- BLOQUEOS
CREATE TABLE BLOQUEOS (
    id_bloqueo NUMBER PRIMARY KEY,
    id_socio NUMBER NOT NULL REFERENCES SOCIOS(id_socio),
    id_usuario_registra NUMBER REFERENCES USUARIOS(id_usuario),
    motivo VARCHAR2(200) NOT NULL,
    tipo_bloqueo VARCHAR2(30) DEFAULT 'CUOTA_VENCIDA',
    fecha_inicio DATE DEFAULT SYSDATE,
    fecha_fin DATE,
    activo NUMBER(1) DEFAULT 1
);

-- MOVILES
CREATE TABLE MOVILES (
    id_movil NUMBER PRIMARY KEY,
    id_socio NUMBER NOT NULL REFERENCES SOCIOS(id_socio),
    patente VARCHAR2(10) UNIQUE NOT NULL,
    marca VARCHAR2(50),
    modelo VARCHAR2(50),
    anio NUMBER(4),
    color VARCHAR2(30),
    estado_operativo VARCHAR2(20) DEFAULT 'DISPONIBLE',
    fecha_registro DATE DEFAULT SYSDATE
);

-- FILA_BASE
CREATE TABLE FILA_BASE (
    id_fila NUMBER PRIMARY KEY,
    id_movil NUMBER NOT NULL REFERENCES MOVILES(id_movil),
    posicion NUMBER NOT NULL,
    fecha_ingreso TIMESTAMP DEFAULT SYSTIMESTAMP,
    fecha_llamado TIMESTAMP,
    fecha_salida TIMESTAMP,
    estado VARCHAR2(20) DEFAULT 'EN_ESPERA',
    CONSTRAINT chk_fila_estado CHECK (estado IN ('EN_ESPERA','LLAMADO','RETIRADO'))
);

-- PASAJEROS
CREATE TABLE PASAJEROS (
    id_pasajero NUMBER PRIMARY KEY,
    rut VARCHAR2(12) UNIQUE NOT NULL,
    nombre VARCHAR2(100) NOT NULL,
    apellido VARCHAR2(100) NOT NULL,
    telefono VARCHAR2(20),
    direccion_frecuente VARCHAR2(200),
    fecha_registro DATE DEFAULT SYSDATE,
    activo NUMBER(1) DEFAULT 1
);

-- SOLICITUDES
CREATE TABLE SOLICITUDES (
    id_solicitud NUMBER PRIMARY KEY,
    id_pasajero NUMBER REFERENCES PASAJEROS(id_pasajero),
    id_movil NUMBER REFERENCES MOVILES(id_movil),
    id_usuario_central NUMBER REFERENCES USUARIOS(id_usuario),
    folio VARCHAR2(20) UNIQUE NOT NULL,
    origen VARCHAR2(200) NOT NULL,
    destino VARCHAR2(200) NOT NULL,
    fecha_hora TIMESTAMP DEFAULT SYSTIMESTAMP,
    estado VARCHAR2(20) DEFAULT 'PENDIENTE',
    canal_entrada VARCHAR2(20) DEFAULT 'TELEFONO',
    observaciones VARCHAR2(500),
    fecha_asignacion TIMESTAMP,
    fecha_inicio TIMESTAMP,
    fecha_termino TIMESTAMP
);

-- HISTORIAL_EVENTOS
CREATE TABLE HISTORIAL_EVENTOS (
    id_evento NUMBER PRIMARY KEY,
    id_usuario NUMBER REFERENCES USUARIOS(id_usuario),
    entidad_tipo VARCHAR2(30) NOT NULL,
    entidad_id NUMBER NOT NULL,
    evento VARCHAR2(100) NOT NULL,
    estado_anterior VARCHAR2(50),
    estado_nuevo VARCHAR2(50),
    detalle VARCHAR2(500),
    ip_origen VARCHAR2(45),
    fecha_hora TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT chk_hist_entidad CHECK (entidad_tipo IN (
        'SOLICITUD','BLOQUEO','CUOTA','MOVIL','SOCIO','USUARIO','PASAJERO','FILA_BASE'
    ))
);

EXIT;
