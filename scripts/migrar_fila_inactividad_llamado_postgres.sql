-- Fila virtual: salida por inactividad y llamado con "Voy" (3 minutos).
--   motivo_salida  : por que salio de la fila el sistema ('inactividad' | 'no_respondio').
--                    NULL cuando sale por accion de una persona (retiro del paletero, etc.).
--   confirmado_en  : cuando el conductor pulso "Voy" tras ser llamado.
--   no_respuestas  : llamados seguidos que no confirmo; con 2 se retira. Vuelve a 0 al confirmar.
-- Idempotente -- se puede correr mas de una vez.
--
-- Uso:
--   psql -U postgres -h localhost -d taxiasiste_dev  -f scripts/migrar_fila_inactividad_llamado_postgres.sql
--   psql -U postgres -h localhost -d taxiasiste_test -f scripts/migrar_fila_inactividad_llamado_postgres.sql
--   (produccion: mismo comando contra taxiasiste_prod con el usuario de la app)

ALTER TABLE "FILA_BASE" ADD COLUMN IF NOT EXISTS motivo_salida VARCHAR(30);
ALTER TABLE "FILA_BASE" ADD COLUMN IF NOT EXISTS confirmado_en TIMESTAMP;
ALTER TABLE "FILA_BASE" ADD COLUMN IF NOT EXISTS no_respuestas INTEGER NOT NULL DEFAULT 0;
