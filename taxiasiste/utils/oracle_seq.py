from django.db import connection


def nextval(sequence_name: str) -> int:
    """Obtiene el siguiente valor de una secuencia Oracle."""
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT {sequence_name}.NEXTVAL FROM DUAL')
        return int(cursor.fetchone()[0])
