-- Verificacion rapida de datos cargados (roles, usuarios, socios, moviles, etc.)

SELECT id_rol, nombre_rol, descripcion, activo FROM ROLES ORDER BY id_rol;

SELECT id_usuario, id_rol, username, email, estado, fecha_creacion FROM USUARIOS ORDER BY id_usuario;

SELECT id_socio, id_usuario, rut, nombre, apellido, telefono, estado_socio, fecha_ingreso FROM SOCIOS ORDER BY id_socio;

SELECT id_movil, id_socio, patente, marca, modelo, anio, estado_operativo FROM MOVILES ORDER BY id_movil;

SELECT id_cuota, id_socio, periodo, monto, estado_pago, fecha_vencimiento, fecha_pago FROM CUOTAS ORDER BY id_cuota;

SELECT id_bloqueo, id_socio, id_usuario_registra, motivo, tipo_bloqueo, fecha_inicio, fecha_fin, activo FROM BLOQUEOS ORDER BY id_bloqueo;

SELECT id_pasajero, rut, nombre, apellido, telefono, activo FROM PASAJEROS ORDER BY id_pasajero;

SELECT id_solicitud, id_pasajero, id_movil, folio, origen, destino, estado, canal_entrada, fecha_hora FROM SOLICITUDES ORDER BY id_solicitud;

SELECT id_evento, id_usuario, entidad_tipo, entidad_id, evento, fecha_hora FROM HISTORIAL_EVENTOS ORDER BY id_evento;

SELECT id_movimiento, id_usuario_registra, id_cuota, tipo, categoria, monto, fecha FROM TESORERIA_MOVIMIENTOS ORDER BY id_movimiento;

-- Conteo general de filas por tabla
SELECT 'ROLES' tabla, COUNT(*) filas FROM ROLES
UNION ALL SELECT 'USUARIOS', COUNT(*) FROM USUARIOS
UNION ALL SELECT 'SOCIOS', COUNT(*) FROM SOCIOS
UNION ALL SELECT 'MOVILES', COUNT(*) FROM MOVILES
UNION ALL SELECT 'CUOTAS', COUNT(*) FROM CUOTAS
UNION ALL SELECT 'BLOQUEOS', COUNT(*) FROM BLOQUEOS
UNION ALL SELECT 'PASAJEROS', COUNT(*) FROM PASAJEROS
UNION ALL SELECT 'SOLICITUDES', COUNT(*) FROM SOLICITUDES
UNION ALL SELECT 'HISTORIAL_EVENTOS', COUNT(*) FROM HISTORIAL_EVENTOS
UNION ALL SELECT 'TESORERIA_MOVIMIENTOS', COUNT(*) FROM TESORERIA_MOVIMIENTOS;
