import sys
import oracledb
from decouple import config


def parse_statements(text: str):
    lines = text.splitlines()
    statements = []
    buffer = []
    in_block = False
    for line in lines:
        stripped = line.strip()
        if stripped == "/":
            if buffer:
                statements.append("\n".join(buffer))
            buffer = []
            in_block = False
            continue
        if stripped.upper() == "BEGIN":
            in_block = True
        if stripped.upper() in ("EXIT;", "EXIT"):
            continue
        if stripped == "" or stripped.startswith("--"):
            continue
        buffer.append(line)
        if not in_block and stripped.endswith(";"):
            stmt = "\n".join(buffer).rstrip()
            if stmt.endswith(";"):
                stmt = stmt[:-1]
            statements.append(stmt)
            buffer = []
    if buffer:
        statements.append("\n".join(buffer))
    return statements


def main(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    statements = parse_statements(text)

    dsn = oracledb.makedsn(
        config("ORACLE_HOST"),
        config("ORACLE_PORT", cast=int),
        service_name=config("ORACLE_SERVICE_NAME", default=None) or None,
        sid=config("ORACLE_SID", default=None) or None,
    )
    conn = oracledb.connect(
        user=config("ORACLE_USER"),
        password=config("ORACLE_PASSWORD"),
        dsn=dsn,
    )
    cur = conn.cursor()

    for stmt in statements:
        s = stmt.strip()
        if not s:
            continue
        if s.upper() == "COMMIT":
            conn.commit()
            print("COMMIT ok")
            continue
        try:
            cur.execute(s)
            first_line = s.splitlines()[0][:80]
            print(f"OK: {first_line}")
        except oracledb.DatabaseError as e:
            (error,) = e.args
            first_line = s.splitlines()[0][:80]
            # ORA-02289: sequence does not exist (DROP SEQUENCE de algo que no existe)
            # ORA-00001: unique constraint violado (fila duplicada, ya insertada)
            # ORA-00942: tabla/vista no existe
            if error.code in (2289, 1, 942):
                print(f"SKIP ({error.code}): {first_line}")
                continue
            print(f"ERROR: {first_line}\n  {error.message}")
            raise

    conn.commit()
    cur.close()
    conn.close()
    print("Listo.")


if __name__ == "__main__":
    main(sys.argv[1])
