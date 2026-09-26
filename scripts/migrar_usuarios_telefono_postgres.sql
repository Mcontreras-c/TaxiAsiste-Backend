-- Agrega telefono a USUARIOS (perfil editable del personal del sindicato).
-- Un Conductor sigue usando SOCIOS.telefono: el perfil lee y escribe ahi.
-- Idempotente -- se puede correr mas de una vez.
--
-- Uso:
--   psql -U postgres -h localhost -d taxiasiste_dev  -f scripts/migrar_usuarios_telefono_postgres.sql
--   psql -U postgres -h localhost -d taxiasiste_test -f scripts/migrar_usuarios_telefono_postgres.sql

ALTER TABLE "USUARIOS" ADD COLUMN IF NOT EXISTS telefono VARCHAR(20);
