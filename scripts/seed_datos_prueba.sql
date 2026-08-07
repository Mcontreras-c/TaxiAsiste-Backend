-- Datos de prueba para desarrollo local (mismos usuarios/datos usados en el equipo)
-- Seguro de re-ejecutar: ignora filas duplicadas (ORA-00001) sin detener el script
-- Requiere que create_business_schema.sql y upgrade_local_schema.sql ya se hayan corrido

-- ===================== ROLES =====================
BEGIN
  INSERT INTO ROLES (id_rol, nombre_rol, descripcion, activo) VALUES
    (seq_roles.NEXTVAL, 'Administrador', 'Acceso total al sistema', 1);
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO ROLES (id_rol, nombre_rol, descripcion, activo) VALUES
    (seq_roles.NEXTVAL, 'Central', 'Central telefonica', 1);
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO ROLES (id_rol, nombre_rol, descripcion, activo) VALUES
    (seq_roles.NEXTVAL, 'Tesorero', 'Gestion de cuotas y tesoreria', 1);
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO ROLES (id_rol, nombre_rol, descripcion, activo) VALUES
    (seq_roles.NEXTVAL, 'Conductor', 'Socio conductor', 1);
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO ROLES (id_rol, nombre_rol, descripcion, activo) VALUES
    (seq_roles.NEXTVAL, 'Paletero', 'Paletero de base', 1);
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/

-- ===================== USUARIOS =====================
-- Password real de cada uno = <username>123 (ej: admin -> admin123)
BEGIN
  INSERT INTO USUARIOS (id_usuario, id_rol, username, password_hash, email, estado, fecha_creacion)
  SELECT seq_usuarios.NEXTVAL, id_rol, 'admin',
    'pbkdf2_sha256$1200000$M9SPS0NJV4HxO8vAkIK7Xa$/iNYlTVIJmQns2e0m1WXJDUW8NjT3qMZ5trnTnxpcUI=',
    'admin@taxiasiste.cl', 'ACTIVO', SYSDATE
  FROM ROLES WHERE nombre_rol = 'Administrador';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO USUARIOS (id_usuario, id_rol, username, password_hash, email, estado, fecha_creacion)
  SELECT seq_usuarios.NEXTVAL, id_rol, 'central',
    'pbkdf2_sha256$1200000$Tz92bdX9g6QZdsoSSV6mBY$VcklpkvvN3+FTbZ9i6/LxdVHddCBnqnD+5Y8dYbaaoc=',
    'central@taxiasiste.cl', 'ACTIVO', SYSDATE
  FROM ROLES WHERE nombre_rol = 'Central';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO USUARIOS (id_usuario, id_rol, username, password_hash, email, estado, fecha_creacion)
  SELECT seq_usuarios.NEXTVAL, id_rol, 'tesorero',
    'pbkdf2_sha256$1200000$XZhTRXjQzCpccbVpXYMzQQ$erp+o1PAts4eg3X+0F+d/k2xCK8ZXBClCPZhkbBo+3c=',
    'tesorero@taxiasiste.cl', 'ACTIVO', SYSDATE
  FROM ROLES WHERE nombre_rol = 'Tesorero';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO USUARIOS (id_usuario, id_rol, username, password_hash, email, estado, fecha_creacion)
  SELECT seq_usuarios.NEXTVAL, id_rol, 'conductor',
    'pbkdf2_sha256$1200000$XYak1mAEwbLBKBNeBoubuU$PJB6wvzd8c11ddSduVIu2H1RbgAqXLqt6lDJsLWUOiI=',
    'conductor@taxiasiste.cl', 'ACTIVO', SYSDATE
  FROM ROLES WHERE nombre_rol = 'Conductor';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO USUARIOS (id_usuario, id_rol, username, password_hash, email, estado, fecha_creacion)
  SELECT seq_usuarios.NEXTVAL, id_rol, 'paletero',
    'pbkdf2_sha256$1200000$r5YAGwfPfWqcdHGDAopHoL$qpjohQLkrvV7L5VPIySI2+OUW9rUqvFPEKDsyWKSXMk=',
    'paletero@taxiasiste.cl', 'ACTIVO', SYSDATE
  FROM ROLES WHERE nombre_rol = 'Paletero';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/

-- ===================== SOCIOS =====================
BEGIN
  INSERT INTO SOCIOS (id_socio, id_usuario, rut, nombre, apellido, telefono, direccion, estado_socio, fecha_ingreso)
  SELECT seq_socios.NEXTVAL, id_usuario, '12345678-9', 'Juan', 'Perez', '912345678', 'Av. Principal 123', 'ACTIVO', SYSDATE
  FROM USUARIOS WHERE username = 'conductor';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO SOCIOS (id_socio, id_usuario, rut, nombre, apellido, telefono, direccion, estado_socio, fecha_ingreso) VALUES
    (seq_socios.NEXTVAL, NULL, '87654321-0', 'Rodrigo', 'Vega', '922876543', 'Pasaje Sur 5', 'BLOQUEADO', SYSDATE);
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO SOCIOS (id_socio, id_usuario, rut, nombre, apellido, telefono, direccion, estado_socio, fecha_ingreso) VALUES
    (seq_socios.NEXTVAL, NULL, '98765432-1', 'Pedro', 'Soto', '911987654', 'Calle Norte 22', 'ACTIVO', SYSDATE);
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/

-- ===================== MOVILES =====================
BEGIN
  INSERT INTO MOVILES (id_movil, id_socio, patente, marca, modelo, anio, color, estado_operativo, fecha_registro)
  SELECT seq_moviles.NEXTVAL, id_socio, 'ABCD12', 'Toyota', 'Corolla', 2020, 'Blanco', 'DISPONIBLE', SYSDATE
  FROM SOCIOS WHERE rut = '12345678-9';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO MOVILES (id_movil, id_socio, patente, marca, modelo, anio, color, estado_operativo, fecha_registro)
  SELECT seq_moviles.NEXTVAL, id_socio, 'MNOP56', 'Kia', 'Rio', 2021, 'Gris', 'BLOQUEADO', SYSDATE
  FROM SOCIOS WHERE rut = '87654321-0';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO MOVILES (id_movil, id_socio, patente, marca, modelo, anio, color, estado_operativo, fecha_registro)
  SELECT seq_moviles.NEXTVAL, id_socio, 'WXYZ34', 'Hyundai', 'Accent', 2019, 'Negro', 'DISPONIBLE', SYSDATE
  FROM SOCIOS WHERE rut = '98765432-1';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/

-- ===================== CUOTAS =====================
BEGIN
  INSERT INTO CUOTAS (id_cuota, id_socio, periodo, monto, estado_pago, fecha_vencimiento, fecha_pago)
  SELECT seq_cuotas.NEXTVAL, id_socio, DATE '2026-05-01', 50000, 'PAGADO', DATE '2026-05-31', DATE '2026-05-20'
  FROM SOCIOS WHERE rut = '12345678-9';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO CUOTAS (id_cuota, id_socio, periodo, monto, estado_pago, fecha_vencimiento, fecha_pago)
  SELECT seq_cuotas.NEXTVAL, id_socio, DATE '2026-06-01', 50000, 'VENCIDO', DATE '2026-06-30', NULL
  FROM SOCIOS WHERE rut = '12345678-9';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO CUOTAS (id_cuota, id_socio, periodo, monto, estado_pago, fecha_vencimiento, fecha_pago)
  SELECT seq_cuotas.NEXTVAL, id_socio, DATE '2026-07-01', 50000, 'PENDIENTE', DATE '2026-07-31', NULL
  FROM SOCIOS WHERE rut = '12345678-9';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/

-- ===================== PASAJEROS =====================
BEGIN
  INSERT INTO PASAJEROS (id_pasajero, rut, nombre, apellido, telefono, direccion_frecuente, fecha_registro, activo) VALUES
    (seq_pasajeros.NEXTVAL, '11222333-4', 'Maria', 'Lopez', '934333333', 'Av. Central 100', SYSDATE, 1);
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO PASAJEROS (id_pasajero, rut, nombre, apellido, telefono, direccion_frecuente, fecha_registro, activo) VALUES
    (seq_pasajeros.NEXTVAL, '55666777-8', 'Jorge', 'Castillo', '945666777', 'Camino Real 400', SYSDATE, 1);
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO PASAJEROS (id_pasajero, rut, nombre, apellido, telefono, direccion_frecuente, fecha_registro, activo) VALUES
    (seq_pasajeros.NEXTVAL, '77888999-0', 'Claudia', 'Fernandez', '956888999', 'Villa Alegre 300', SYSDATE, 1);
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/

-- ===================== SOLICITUDES =====================
BEGIN
  INSERT INTO SOLICITUDES (id_solicitud, id_pasajero, id_movil, folio, origen, destino, fecha_hora, estado, canal_entrada)
  SELECT seq_solicitudes.NEXTVAL, p.id_pasajero, NULL, 'SOL-2026-SEED1', 'Los Pinos 789', 'Hospital Regional', SYSTIMESTAMP, 'PENDIENTE', 'TELEFONO'
  FROM PASAJEROS p WHERE p.rut = '11222333-4';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/
BEGIN
  INSERT INTO SOLICITUDES (id_solicitud, id_pasajero, id_movil, folio, origen, destino, fecha_hora, estado, canal_entrada, fecha_asignacion, fecha_inicio, fecha_termino)
  SELECT seq_solicitudes.NEXTVAL, p.id_pasajero, m.id_movil, 'SOL-2026-SEED2', 'Camino Real 400', 'Aeropuerto', SYSTIMESTAMP - 1, 'COMPLETADO', 'APP',
         SYSTIMESTAMP - 1, SYSTIMESTAMP - 1, SYSTIMESTAMP - 1
  FROM PASAJEROS p, MOVILES m WHERE p.rut = '55666777-8' AND m.patente = 'ABCD12';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1 THEN RAISE; END IF;
END;
/

COMMIT;
EXIT;
