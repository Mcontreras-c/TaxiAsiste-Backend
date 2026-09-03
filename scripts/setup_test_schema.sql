-- Usuario Oracle dedicado para tests automatizados (pytest). Mismo esquema
-- de negocio que taxiasiste_app pero en su propio schema, para que correr la
-- suite de tests nunca toque ni un registro de la base de desarrollo.
-- Ejecutar como SYSTEM en XEPDB1, una sola vez por maquina/CI.

ALTER SESSION SET CONTAINER = XEPDB1;

CREATE USER taxiasiste_test IDENTIFIED BY "TaxiAsiste_Test_2026";

GRANT CONNECT, RESOURCE TO taxiasiste_test;
GRANT UNLIMITED TABLESPACE TO taxiasiste_test;

EXIT;
