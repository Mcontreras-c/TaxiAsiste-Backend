"""
Reglas de negocio de las reservas, sin acceso a base de datos (funciones
puras: se prueban sin fixtures).

La franja que "ocupa" una reserva en la agenda de un conductor:

    inicio = recogida - duracion - margen   (hora maxima para salir del hospital)
    fin    = recogida + duracion + margen   (vuelve a quedar libre en el hospital)

Como TODOS los viajes terminan en el hospital (DESTINO_UNICO), el mismo
`duracion` sirve para la ida (hospital -> punto de recogida) y para el viaje
(recogida -> hospital). Dos reservas del mismo conductor no pueden solaparse.
"""

from datetime import timedelta, timezone as tz_utc

from django.conf import settings
from django.utils import timezone


def aware(dt):
    """
    Las columnas TIMESTAMP de esta base guardan UTC sin zona, y al leerlas
    Django las devuelve "ingenuas" (sin tzinfo): comparar una con timezone.now()
    da TypeError y serializarla a mano las deja sin 'Z' (el navegador la
    interpretaria como hora local). Se normaliza aca, en un solo lugar.
    """
    if dt is not None and timezone.is_naive(dt):
        return dt.replace(tzinfo=tz_utc.utc)
    return dt


def margen():
    return timedelta(minutes=settings.RESERVA_MARGEN_MIN)


def franja(recogida, duracion_s):
    """(inicio, fin) de la franja que ocupa una reserva."""
    recogida = aware(recogida)
    duracion = timedelta(seconds=duracion_s)
    return recogida - duracion - margen(), recogida + duracion + margen()


def hora_maxima_salida(recogida, duracion_s):
    """Hora limite para salir del hospital (y por tanto de la fila virtual) rumbo a esta reserva."""
    return franja(recogida, duracion_s)[0]


def alerta(estado, recogida, duracion_s, ahora):
    """
    Alerta que Central debe atender, calculada al leer (no hace falta una tarea
    programada):

    - 'SIN_CONDUCTOR': nadie tomo la reserva y ya falta poco (a
      RESERVA_ALERTA_SIN_CONDUCTOR_MIN de la hora maxima de salida) -> Central
      debe asignarla por telefono.
    - 'NO_CONFIRMADA': un conductor la tomo pero paso su hora maxima de salida
      (mas la tolerancia) y no pulso "Voy en camino" -> Central lo llama.
    """
    salida = hora_maxima_salida(recogida, duracion_s)
    if estado == 'PROGRAMADA' and ahora >= salida - timedelta(minutes=settings.RESERVA_ALERTA_SIN_CONDUCTOR_MIN):
        return 'SIN_CONDUCTOR'
    if estado == 'ASIGNADA' and ahora >= salida + timedelta(minutes=settings.RESERVA_TOLERANCIA_CONFIRMACION_MIN):
        return 'NO_CONFIRMADA'
    return None


def se_cruzan(a, b):
    """
    a y b son (recogida, duracion_s). Solo se permite una reserva cuando la
    franja de una termina antes (o justo cuando) empieza la otra.
    """
    inicio_a, fin_a = franja(*a)
    inicio_b, fin_b = franja(*b)
    return inicio_a < fin_b and inicio_b < fin_a
