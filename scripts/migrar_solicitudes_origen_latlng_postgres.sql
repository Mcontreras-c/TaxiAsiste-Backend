-- Agrega origen_lat/origen_lng a SOLICITUDES para bases ya provisionadas
-- (taxiasiste_dev, taxiasiste_test) antes de que create_business_schema_postgres.sql
-- incluyera estas columnas. Idempotente -- se puede correr mas de una vez.
--
-- Uso:
--   psql -U postgres -h localhost -d taxiasiste_dev  -f scripts/migrar_solicitudes_origen_latlng_postgres.sql
--   psql -U postgres -h localhost -d taxiasiste_test -f scripts/migrar_solicitudes_origen_latlng_postgres.sql

ALTER TABLE "SOLICITUDES" ADD COLUMN IF NOT EXISTS origen_lat NUMERIC(10, 6);
ALTER TABLE "SOLICITUDES" ADD COLUMN IF NOT EXISTS origen_lng NUMERIC(10, 6);
