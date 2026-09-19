-- Base Postgres dedicada para tests automatizados (pytest). Mismo esquema
-- de negocio que taxiasiste_dev pero en su propia base, para que correr la
-- suite de tests nunca toque ni un registro de la base de desarrollo.
--
-- Ejecutar como postgres (o el superusuario configurado), una sola vez por
-- maquina/CI:
--   psql -U postgres -h localhost -f scripts/setup_test_schema.sql
--   psql -U postgres -h localhost -d taxiasiste_test -f scripts/create_business_schema_postgres.sql
--   DJANGO_SETTINGS_MODULE=taxiasiste.settings_test python manage.py migrate

CREATE DATABASE taxiasiste_test;
