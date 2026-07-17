-- Parches para instancias migradas desde otro equipo (solo lo que falta)
-- Seguro de re-ejecutar: ignora objetos ya existentes

BEGIN
    EXECUTE IMMEDIATE 'CREATE SEQUENCE seq_fila_base START WITH 1 INCREMENT BY 1 NOCACHE';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE '
        CREATE TABLE FILA_BASE (
            id_fila NUMBER PRIMARY KEY,
            id_movil NUMBER NOT NULL REFERENCES MOVILES(id_movil),
            posicion NUMBER NOT NULL,
            fecha_ingreso TIMESTAMP DEFAULT SYSTIMESTAMP,
            fecha_llamado TIMESTAMP,
            fecha_salida TIMESTAMP,
            estado VARCHAR2(20) DEFAULT ''EN_ESPERA'',
            CONSTRAINT chk_fila_estado CHECK (estado IN (''EN_ESPERA'',''LLAMADO'',''RETIRADO''))
        )';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -955 THEN RAISE; END IF;
END;
/

EXIT;
