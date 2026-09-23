-- Agrega nombre/apellido a USUARIOS y el rol Secretario (usado por Agenda y
-- por "Gestion de Usuarios") a bases ya provisionadas antes de estos cambios.
-- Idempotente -- se puede correr mas de una vez.
--
-- Uso:
--   psql -U postgres -h localhost -d taxiasiste_dev  -f scripts/migrar_usuarios_nombre_apellido_postgres.sql
--   psql -U postgres -h localhost -d taxiasiste_test -f scripts/migrar_usuarios_nombre_apellido_postgres.sql

ALTER TABLE "USUARIOS" ADD COLUMN IF NOT EXISTS nombre VARCHAR(100);
ALTER TABLE "USUARIOS" ADD COLUMN IF NOT EXISTS apellido VARCHAR(100);

INSERT INTO "ROLES" (id_rol, nombre_rol, descripcion, activo)
VALUES (nextval('seq_roles'), 'Secretario', 'Secretaria del sindicato -- agenda y documentos', 1)
ON CONFLICT (nombre_rol) DO NOTHING;
