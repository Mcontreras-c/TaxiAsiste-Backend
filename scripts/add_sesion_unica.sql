-- Agrega columna para forzar sesion unica por usuario (login nuevo invalida
-- el JWT anterior). Seguro de re-ejecutar: ignora la columna si ya existe.

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE USUARIOS ADD sesion_actual VARCHAR2(64)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN RAISE; END IF; -- ORA-01430: la columna ya existe
END;
/

EXIT;
