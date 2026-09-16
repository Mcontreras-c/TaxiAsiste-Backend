-- Datos de prueba para desarrollo local -- version PostgreSQL
-- Seguro de re-ejecutar: ON CONFLICT DO NOTHING evita duplicados
-- Requiere que create_business_schema_postgres.sql ya se haya corrido

-- ===================== "ROLES" =====================
INSERT INTO "ROLES" (id_rol, nombre_rol, descripcion, activo) VALUES
  (nextval('seq_roles'), 'Administrador', 'Acceso total al sistema', 1)
  ON CONFLICT (nombre_rol) DO NOTHING;
INSERT INTO "ROLES" (id_rol, nombre_rol, descripcion, activo) VALUES
  (nextval('seq_roles'), 'Central', 'Central telefonica', 1)
  ON CONFLICT (nombre_rol) DO NOTHING;
INSERT INTO "ROLES" (id_rol, nombre_rol, descripcion, activo) VALUES
  (nextval('seq_roles'), 'Tesorero', 'Gestion de cuotas y tesoreria', 1)
  ON CONFLICT (nombre_rol) DO NOTHING;
INSERT INTO "ROLES" (id_rol, nombre_rol, descripcion, activo) VALUES
  (nextval('seq_roles'), 'Conductor', 'Socio conductor', 1)
  ON CONFLICT (nombre_rol) DO NOTHING;
INSERT INTO "ROLES" (id_rol, nombre_rol, descripcion, activo) VALUES
  (nextval('seq_roles'), 'Paletero', 'Paletero de base', 1)
  ON CONFLICT (nombre_rol) DO NOTHING;

-- ===================== "USUARIOS" =====================
-- Password real de cada uno = <username>123 (ej: admin -> admin123)
INSERT INTO "USUARIOS" (id_usuario, id_rol, username, password_hash, email, estado, fecha_creacion)
  SELECT nextval('seq_usuarios'), id_rol, 'admin',
    'pbkdf2_sha256$1200000$M9SPS0NJV4HxO8vAkIK7Xa$/iNYlTVIJmQns2e0m1WXJDUW8NjT3qMZ5trnTnxpcUI=',
    'admin@taxiasiste.cl', 'ACTIVO', CURRENT_DATE
  FROM "ROLES" WHERE nombre_rol = 'Administrador'
  ON CONFLICT (username) DO NOTHING;
INSERT INTO "USUARIOS" (id_usuario, id_rol, username, password_hash, email, estado, fecha_creacion)
  SELECT nextval('seq_usuarios'), id_rol, 'central',
    'pbkdf2_sha256$1200000$Tz92bdX9g6QZdsoSSV6mBY$VcklpkvvN3+FTbZ9i6/LxdVHddCBnqnD+5Y8dYbaaoc=',
    'central@taxiasiste.cl', 'ACTIVO', CURRENT_DATE
  FROM "ROLES" WHERE nombre_rol = 'Central'
  ON CONFLICT (username) DO NOTHING;
INSERT INTO "USUARIOS" (id_usuario, id_rol, username, password_hash, email, estado, fecha_creacion)
  SELECT nextval('seq_usuarios'), id_rol, 'tesorero',
    'pbkdf2_sha256$1200000$XZhTRXjQzCpccbVpXYMzQQ$erp+o1PAts4eg3X+0F+d/k2xCK8ZXBClCPZhkbBo+3c=',
    'tesorero@taxiasiste.cl', 'ACTIVO', CURRENT_DATE
  FROM "ROLES" WHERE nombre_rol = 'Tesorero'
  ON CONFLICT (username) DO NOTHING;
INSERT INTO "USUARIOS" (id_usuario, id_rol, username, password_hash, email, estado, fecha_creacion)
  SELECT nextval('seq_usuarios'), id_rol, 'conductor',
    'pbkdf2_sha256$1200000$XYak1mAEwbLBKBNeBoubuU$PJB6wvzd8c11ddSduVIu2H1RbgAqXLqt6lDJsLWUOiI=',
    'conductor@taxiasiste.cl', 'ACTIVO', CURRENT_DATE
  FROM "ROLES" WHERE nombre_rol = 'Conductor'
  ON CONFLICT (username) DO NOTHING;
INSERT INTO "USUARIOS" (id_usuario, id_rol, username, password_hash, email, estado, fecha_creacion)
  SELECT nextval('seq_usuarios'), id_rol, 'paletero',
    'pbkdf2_sha256$1200000$r5YAGwfPfWqcdHGDAopHoL$qpjohQLkrvV7L5VPIySI2+OUW9rUqvFPEKDsyWKSXMk=',
    'paletero@taxiasiste.cl', 'ACTIVO', CURRENT_DATE
  FROM "ROLES" WHERE nombre_rol = 'Paletero'
  ON CONFLICT (username) DO NOTHING;

-- ===================== "SOCIOS" =====================
INSERT INTO "SOCIOS" (id_socio, id_usuario, rut, nombre, apellido, telefono, direccion, estado_socio, fecha_ingreso)
  SELECT nextval('seq_socios'), id_usuario, '12345678-9', 'Juan', 'Perez', '912345678', 'Av. Principal 123', 'ACTIVO', CURRENT_DATE
  FROM "USUARIOS" WHERE username = 'conductor'
  ON CONFLICT (rut) DO NOTHING;
INSERT INTO "SOCIOS" (id_socio, id_usuario, rut, nombre, apellido, telefono, direccion, estado_socio, fecha_ingreso) VALUES
  (nextval('seq_socios'), NULL, '87654321-0', 'Rodrigo', 'Vega', '922876543', 'Pasaje Sur 5', 'BLOQUEADO', CURRENT_DATE)
  ON CONFLICT (rut) DO NOTHING;
INSERT INTO "SOCIOS" (id_socio, id_usuario, rut, nombre, apellido, telefono, direccion, estado_socio, fecha_ingreso) VALUES
  (nextval('seq_socios'), NULL, '98765432-1', 'Pedro', 'Soto', '911987654', 'Calle Norte 22', 'ACTIVO', CURRENT_DATE)
  ON CONFLICT (rut) DO NOTHING;

-- ===================== "MOVILES" =====================
INSERT INTO "MOVILES" (id_movil, id_socio, patente, marca, modelo, anio, color, estado_operativo, fecha_registro)
  SELECT nextval('seq_moviles'), id_socio, 'ABCD12', 'Toyota', 'Corolla', 2020, 'Blanco', 'DISPONIBLE', CURRENT_DATE
  FROM "SOCIOS" WHERE rut = '12345678-9'
  ON CONFLICT (patente) DO NOTHING;
INSERT INTO "MOVILES" (id_movil, id_socio, patente, marca, modelo, anio, color, estado_operativo, fecha_registro)
  SELECT nextval('seq_moviles'), id_socio, 'MNOP56', 'Kia', 'Rio', 2021, 'Gris', 'BLOQUEADO', CURRENT_DATE
  FROM "SOCIOS" WHERE rut = '87654321-0'
  ON CONFLICT (patente) DO NOTHING;
INSERT INTO "MOVILES" (id_movil, id_socio, patente, marca, modelo, anio, color, estado_operativo, fecha_registro)
  SELECT nextval('seq_moviles'), id_socio, 'WXYZ34', 'Hyundai', 'Accent', 2019, 'Negro', 'DISPONIBLE', CURRENT_DATE
  FROM "SOCIOS" WHERE rut = '98765432-1'
  ON CONFLICT (patente) DO NOTHING;

-- ===================== "CUOTAS" (pagada, vencida, pendiente) =====================
INSERT INTO "CUOTAS" (id_cuota, id_socio, periodo, monto, estado_pago, fecha_vencimiento, fecha_pago)
  SELECT nextval('seq_cuotas'), id_socio, DATE '2026-05-01', 50000, 'PAGADO', DATE '2026-05-31', DATE '2026-05-20'
  FROM "SOCIOS" WHERE rut = '12345678-9'
  ON CONFLICT (id_socio, periodo) DO NOTHING;
INSERT INTO "CUOTAS" (id_cuota, id_socio, periodo, monto, estado_pago, fecha_vencimiento, fecha_pago)
  SELECT nextval('seq_cuotas'), id_socio, DATE '2026-06-01', 50000, 'VENCIDO', DATE '2026-06-30', NULL
  FROM "SOCIOS" WHERE rut = '12345678-9'
  ON CONFLICT (id_socio, periodo) DO NOTHING;
INSERT INTO "CUOTAS" (id_cuota, id_socio, periodo, monto, estado_pago, fecha_vencimiento, fecha_pago)
  SELECT nextval('seq_cuotas'), id_socio, DATE '2026-07-01', 50000, 'PENDIENTE', DATE '2026-07-31', NULL
  FROM "SOCIOS" WHERE rut = '12345678-9'
  ON CONFLICT (id_socio, periodo) DO NOTHING;

-- ===================== "PASAJEROS" =====================
INSERT INTO "PASAJEROS" (id_pasajero, rut, nombre, apellido, telefono, direccion_frecuente, fecha_registro, activo) VALUES
  (nextval('seq_pasajeros'), '11222333-4', 'Maria', 'Lopez', '934333333', 'Av. Central 100', CURRENT_DATE, 1)
  ON CONFLICT (rut) DO NOTHING;
INSERT INTO "PASAJEROS" (id_pasajero, rut, nombre, apellido, telefono, direccion_frecuente, fecha_registro, activo) VALUES
  (nextval('seq_pasajeros'), '55666777-8', 'Jorge', 'Castillo', '945666777', 'Camino Real 400', CURRENT_DATE, 1)
  ON CONFLICT (rut) DO NOTHING;
INSERT INTO "PASAJEROS" (id_pasajero, rut, nombre, apellido, telefono, direccion_frecuente, fecha_registro, activo) VALUES
  (nextval('seq_pasajeros'), '77888999-0', 'Claudia', 'Fernandez', '956888999', 'Villa Alegre 300', CURRENT_DATE, 1)
  ON CONFLICT (rut) DO NOTHING;

-- ===================== "SOLICITUDES" =====================
-- Una PENDIENTE (para probar "Aceptar solicitud" desde el conductor) y una COMPLETADA (historial)
INSERT INTO "SOLICITUDES" (id_solicitud, id_pasajero, id_movil, folio, origen, destino, fecha_hora, estado, canal_entrada)
  SELECT nextval('seq_solicitudes'), p.id_pasajero, NULL, 'SOL-2026-SEED1', 'Los Pinos 789', 'Hospital Regional', CURRENT_TIMESTAMP, 'PENDIENTE', 'TELEFONO'
  FROM "PASAJEROS" p WHERE p.rut = '11222333-4'
  ON CONFLICT (folio) DO NOTHING;
INSERT INTO "SOLICITUDES" (id_solicitud, id_pasajero, id_movil, folio, origen, destino, fecha_hora, estado, canal_entrada, fecha_asignacion, fecha_inicio, fecha_termino)
  SELECT nextval('seq_solicitudes'), p.id_pasajero, m.id_movil, 'SOL-2026-SEED2', 'Camino Real 400', 'Aeropuerto', CURRENT_TIMESTAMP - INTERVAL '1 day', 'COMPLETADO', 'APP',
         CURRENT_TIMESTAMP - INTERVAL '1 day', CURRENT_TIMESTAMP - INTERVAL '1 day', CURRENT_TIMESTAMP - INTERVAL '1 day'
  FROM "PASAJEROS" p, "MOVILES" m WHERE p.rut = '55666777-8' AND m.patente = 'ABCD12'
  ON CONFLICT (folio) DO NOTHING;
