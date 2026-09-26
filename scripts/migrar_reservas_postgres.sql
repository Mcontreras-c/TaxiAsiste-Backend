-- Reservas: viajes programados (hasta 24 h) que entran por la Central y toma un
-- conductor. Crea RESERVAS y RESERVA_EVENTOS (auditoria: tomada, soltada, etc.).
-- Idempotente -- se puede correr mas de una vez.
--
-- Uso:
--   psql -U postgres -h localhost -d taxiasiste_dev  -f scripts/migrar_reservas_postgres.sql
--   psql -U postgres -h localhost -d taxiasiste_test -f scripts/migrar_reservas_postgres.sql
--   (produccion: mismo comando contra taxiasiste_prod con el usuario de la app)

CREATE SEQUENCE IF NOT EXISTS seq_reservas START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE IF NOT EXISTS seq_reserva_eventos START WITH 1 INCREMENT BY 1;

CREATE TABLE IF NOT EXISTS "RESERVAS" (
    id_reserva INTEGER PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    id_pasajero INTEGER REFERENCES "PASAJEROS"(id_pasajero),
    id_movil INTEGER REFERENCES "MOVILES"(id_movil),
    id_usuario_central INTEGER REFERENCES "USUARIOS"(id_usuario),
    origen VARCHAR(200) NOT NULL,
    origen_lat NUMERIC(10, 6),
    origen_lng NUMERIC(10, 6),
    destino VARCHAR(200) NOT NULL,
    fecha_hora_recogida TIMESTAMP NOT NULL,
    duracion_estimada_s INTEGER NOT NULL,
    distancia_estimada_m INTEGER NOT NULL,
    tarifa_estimada INTEGER NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'PROGRAMADA',
    observaciones VARCHAR(500),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_tomada TIMESTAMP,
    fecha_termino TIMESTAMP,
    CONSTRAINT chk_reserva_estado CHECK (estado IN (
        'PROGRAMADA', 'ASIGNADA', 'EN_CAMINO', 'COMPLETADA', 'CANCELADA', 'INCUMPLIDA'
    ))
);

CREATE INDEX IF NOT EXISTS idx_reservas_estado_recogida ON "RESERVAS" (estado, fecha_hora_recogida);
CREATE INDEX IF NOT EXISTS idx_reservas_movil ON "RESERVAS" (id_movil);

CREATE TABLE IF NOT EXISTS "RESERVA_EVENTOS" (
    id_evento INTEGER PRIMARY KEY,
    id_reserva INTEGER NOT NULL REFERENCES "RESERVAS"(id_reserva),
    id_movil INTEGER REFERENCES "MOVILES"(id_movil),
    id_usuario INTEGER REFERENCES "USUARIOS"(id_usuario),
    tipo VARCHAR(30) NOT NULL,
    detalle VARCHAR(300),
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reserva_eventos_reserva ON "RESERVA_EVENTOS" (id_reserva);
CREATE INDEX IF NOT EXISTS idx_reserva_eventos_movil_tipo ON "RESERVA_EVENTOS" (id_movil, tipo);

-- ---------------------------------------------------------------------------
-- Etapa 2: estado PASAJERO_AUSENTE y registro de incumplimientos de pasajeros.
-- A la 3a vez el pasajero queda bloqueado para pedir moviles a domicilio (un
-- administrador puede levantar el bloqueo, lo que reinicia el contador).
-- ---------------------------------------------------------------------------
ALTER TABLE "RESERVAS" DROP CONSTRAINT IF EXISTS chk_reserva_estado;
ALTER TABLE "RESERVAS" ADD CONSTRAINT chk_reserva_estado CHECK (estado IN (
    'PROGRAMADA', 'ASIGNADA', 'EN_CAMINO', 'COMPLETADA', 'CANCELADA', 'INCUMPLIDA', 'PASAJERO_AUSENTE'
));

ALTER TABLE "PASAJEROS" ADD COLUMN IF NOT EXISTS incumplimientos SMALLINT NOT NULL DEFAULT 0;
ALTER TABLE "PASAJEROS" ADD COLUMN IF NOT EXISTS bloqueado_domicilio SMALLINT NOT NULL DEFAULT 0;
