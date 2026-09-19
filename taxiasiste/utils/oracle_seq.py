from django.db import connection


def nextval(sequence_name: str) -> int:
    """Obtiene el siguiente valor de una secuencia PostgreSQL."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval(%s)", [sequence_name])
        return int(cursor.fetchone()[0])
