import math

import requests
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

# Google Geocoding/Directions exigen la key como query param — por eso esto
# pasa por el backend (clave "TaxiAsiste - Backend", restringida por API) en
# vez de llamarse directo desde el frontend, que usa una clave distinta
# restringida por dominio.
GEOCODING_URL = 'https://maps.googleapis.com/maps/api/geocode/json'
DIRECTIONS_URL = 'https://maps.googleapis.com/maps/api/directions/json'


def _tiene_calle_valida(item):
    """
    Sin un componente de tipo 'route' (calle), Google devolvio algo generico
    (una comuna/region) — no sirve para despacho de taxis puerta a puerta.
    """
    return any('route' in c.get('types', []) for c in item.get('address_components', []))


def _decodificar_polyline(encoded):
    """
    Decodifica el 'overview_polyline' que devuelve Directions (algoritmo
    estandar de Google, precision 1e-5) a una lista de coordenadas [lng, lat]
    — mismo formato GeoJSON que se usaba antes con el LineString de OSRM, asi
    el frontend (MapaDespacho) no tuvo que cambiar nada de como consume esto.
    """
    puntos = []
    index = lat = lng = 0
    largo = len(encoded)
    while index < largo:
        for coordenada in ('lat', 'lng'):
            resultado = desplazamiento = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                resultado |= (b & 0x1f) << desplazamiento
                desplazamiento += 5
                if b < 0x20:
                    break
            delta = ~(resultado >> 1) if resultado & 1 else (resultado >> 1)
            if coordenada == 'lat':
                lat += delta
            else:
                lng += delta
        puntos.append([lng / 1e5, lat / 1e5])
    return puntos


# HEAD ademas de GET: los monitores de disponibilidad (UptimeRobot y similares)
# consultan con HEAD, y un 405 los haria marcar el servicio como caido.
@api_view(['GET', 'HEAD'])
@permission_classes([AllowAny])
def ping(request):
    return Response({
        'status': 'ok',
        'fecha': timezone.now().isoformat(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def descarga_app(request):
    """
    Link de descarga del APK para el boton "Descargar app" del panel web. Vive
    en la configuracion del servidor (APK_DOWNLOAD_URL en el .env) para poder
    cambiarlo al publicar una version nueva sin volver a compilar el frontend.
    Solo con sesion iniciada: no se expone a visitantes.
    """
    return Response({'url': settings.APK_DOWNLOAD_URL or None})


def geocodificar_direccion(direccion, bounds=None):
    """
    Convierte una direccion en texto a lat/lng usando Google Geocoding API.
    Helper compartido por la vista `geocodificar` (usada por el Frontend para
    autocompletar) y por SolicitudViewSet.perform_create (geocodifica el
    origen al crear, para poder calcular distancia/ETA despues sin volver a
    llamar a Google).

    Devuelve (lat, lng, direccion_formateada, error), donde error es None si
    salio bien, 'red' si Google no respondio, o 'no_encontrada' si no se pudo
    ubicar una calle exacta -- perform_create ignora el motivo (siempre es
    best-effort, nunca bloquea la creacion), pero la vista `geocodificar` si
    lo necesita para devolver 502 vs 404 como antes de este refactor.
    """
    direccion = (direccion or '').strip()
    if not direccion:
        return None, None, None, 'no_encontrada'

    try:
        resp = requests.get(
            GEOCODING_URL,
            params={
                'address': direccion,
                'region': 'cl',
                'components': 'country:CL',
                **({'bounds': bounds} if bounds else {}),
                'key': settings.GOOGLE_MAPS_API_KEY,
            },
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return None, None, None, 'red'

    resultados = data.get('results') or []
    if data.get('status') != 'OK' or not resultados or not _tiene_calle_valida(resultados[0]):
        return None, None, None, 'no_encontrada'

    r = resultados[0]
    ubicacion = r['geometry']['location']
    return ubicacion['lat'], ubicacion['lng'], r.get('formatted_address', direccion), None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geocodificar(request):
    """Convierte una direccion en texto a lat/lng usando Google Geocoding API."""
    direccion = request.query_params.get('direccion', '').strip()
    if not direccion:
        return Response({'detail': 'Parametro "direccion" es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

    lat, lng, direccion_formateada, error = geocodificar_direccion(direccion)
    if error == 'red':
        return Response({'detail': 'Servicio de geocodificacion no disponible.'}, status=status.HTTP_502_BAD_GATEWAY)
    if error:
        return Response(
            {'detail': 'No se pudo ubicar la calle exacta de esta dirección.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response({
        'lat': lat,
        'lng': lng,
        'direccion_formateada': direccion_formateada,
    })


def calcular_ruta(origen_lat, origen_lng, destino_lat, destino_lng):
    """
    Llama a Google Directions API para la ruta origen->destino. Helper
    compartido por la vista `ruta` (traza en el mapa) y por
    SolicitudViewSet.pendientes_con_distancia (distancia/ETA del conductor
    hasta el punto de recogida).

    Devuelve (data, error), donde error es None si salio bien, 'red' si
    Google no respondio, o 'sin_ruta' si no encontro una ruta entre los
    puntos -- pendientes_con_distancia ignora el motivo (best-effort, esa
    solicitud simplemente queda sin distancia/ETA), pero la vista `ruta` si
    lo necesita para devolver 502 vs 404 como antes de este refactor.
    """
    try:
        resp = requests.get(
            DIRECTIONS_URL,
            params={
                'origin': f'{origen_lat},{origen_lng}',
                'destination': f'{destino_lat},{destino_lng}',
                'mode': 'driving',
                'region': 'cl',
                'key': settings.GOOGLE_MAPS_API_KEY,
            },
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return None, 'red'

    if data.get('status') != 'OK' or not data.get('routes'):
        return None, 'sin_ruta'
    return data, None


def calcular_ruta_a_destino_texto(origen_lat, origen_lng, destino_texto):
    """
    Como calcular_ruta, pero con el destino como texto en vez de lat/lng --
    Directions API acepta direcciones de texto directamente, asi que no hace
    falta geocodificar el hospital aparte. Usado por estimar_tarifa, ya que
    TaxiAsiste solo traslada a un destino fijo (ver DESTINO_UNICO).
    """
    try:
        resp = requests.get(
            DIRECTIONS_URL,
            params={
                'origin': f'{origen_lat},{origen_lng}',
                'destination': destino_texto,
                'mode': 'driving',
                'region': 'cl',
                'key': settings.GOOGLE_MAPS_API_KEY,
            },
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return None, 'red'

    if data.get('status') != 'OK' or not data.get('routes'):
        return None, 'sin_ruta'
    return data, None


# Tarifa de taxi basico RM: la bajada de bandera y el valor de cada "tic" los
# fija el MTT ($500 y $200 respectivamente); el tramo de distancia por tic se
# puede elegir dentro del margen que da el MTT (190 a 220 m) -- este
# sindicato usa 200 m. El tic de espera (tiempo detenido/trafico) vale lo
# mismo, cada 60 s. Como ambos tics valen igual, el cruce entre cobrar por
# distancia o por tiempo se desprende de esos mismos numeros: 200 m / 60 s =
# 12 km/h -- por eso la estimacion usa el mayor entre "cuanto marcaria si
# fuera puro avance" y "cuanto marcaria si fuera puro tiempo detenido", igual
# que hace el taximetro real cuando el viaje mezcla tramos fluidos con
# tramos de trafico.
BAJADA_DE_BANDERA = 500
VALOR_TIC = 200
METROS_POR_TIC = 200
SEGUNDOS_POR_TIC = 60


def calcular_tarifa_estimada(distancia_m, duracion_s):
    cargo_por_distancia = math.ceil(distancia_m / METROS_POR_TIC) * VALOR_TIC
    cargo_por_tiempo = math.ceil(duracion_s / SEGUNDOS_POR_TIC) * VALOR_TIC
    return BAJADA_DE_BANDERA + max(cargo_por_distancia, cargo_por_tiempo)


# Region Metropolitana (SW|NE): sesga la busqueda de direcciones escritas a
# mano ("Av. Pajaritos 3000") hacia Santiago en vez de una calle homonima de
# otra ciudad. Es solo un sesgo, no una restriccion.
BOUNDS_RM = '-34.3,-71.7|-32.9,-69.9'


PLACES_TEXTSEARCH_URL = 'https://maps.googleapis.com/maps/api/place/textsearch/json'


def _buscar_lugar(texto):
    """
    Busca lo escrito con Places Text Search (el buscador de Google Maps):
    entiende nombres de lugar como "Metro Pudahuel", que Geocoding no ubica
    bien (devuelve una calle cercana). Devuelve (lat, lng, direccion) o None
    si no hay resultado o el servicio no esta disponible/habilitado -- en ese
    caso quien llama cae al geocodificador de direcciones.
    """
    try:
        resp = requests.get(
            PLACES_TEXTSEARCH_URL,
            params={
                'query': texto,
                'region': 'cl',
                'language': 'es',
                'location': '-33.45,-70.67',  # centro de Santiago: sesga, no restringe
                'radius': 50000,
                'key': settings.GOOGLE_MAPS_API_KEY,
            },
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None

    resultados = data.get('results') or []
    if data.get('status') != 'OK' or not resultados:
        return None

    r = resultados[0]
    ubicacion = r['geometry']['location']
    nombre, direccion = r.get('name'), r.get('formatted_address', '')
    etiqueta = f'{nombre}, {direccion}' if nombre and nombre not in direccion else direccion
    return ubicacion['lat'], ubicacion['lng'], etiqueta


def _resolver_punto(texto, lat, lng):
    """
    Un extremo del viaje como (punto, error). Si viene lat/lng se usa tal
    cual (GPS); si viene texto primero se busca como lugar (Places) y, si eso
    no da resultado, se geocodifica como direccion con sesgo a la RM. Siempre
    se devuelve la direccion que Google entendio, para que se pueda verificar.
    """
    if lat is not None and lng is not None:
        return {'lat': lat, 'lng': lng, 'direccion': None}, None
    lugar = _buscar_lugar(texto)
    if lugar:
        return {'lat': lugar[0], 'lng': lugar[1], 'direccion': lugar[2]}, None
    g_lat, g_lng, formateada, error = geocodificar_direccion(texto, bounds=BOUNDS_RM)
    if error:
        return None, error
    return {'lat': g_lat, 'lng': g_lng, 'direccion': formateada}, None


def _parametro_float(params, nombre):
    try:
        return float(params[nombre])
    except (KeyError, ValueError):
        return None


def _error_geocodificacion(error, extremo):
    if error == 'red':
        return Response({'detail': 'Servicio de geocodificacion no disponible.'}, status=status.HTTP_502_BAD_GATEWAY)
    return Response(
        {'detail': f'No se pudo ubicar la calle exacta del {extremo}. Prueba con calle y número.'},
        status=status.HTTP_404_NOT_FOUND,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cotizar_tarifa(request):
    """
    Cotizador de tarifa aproximada para responder "¿cuanto sale a X?" (en la
    salida del hospital o con alguien haciendo parar en la calle).

    Origen: por defecto el hospital (destino fijo de TaxiAsiste); o
    'origen_lat'+'origen_lng' (ubicacion actual); o 'origen_texto'.
    Destino: 'destino_texto' o 'destino_lat'+'destino_lng'.

    Devuelve todas las rutas alternativas que da Google (la primera es la
    recomendada) con su tarifa estimada cada una, ya que el valor depende de
    por donde se vaya. Es una ESTIMACION: el taximetro real depende del
    trafico y del camino que tome el conductor.
    """
    from taxiasiste.solicitudes.models import DESTINO_UNICO

    q = request.query_params
    o_lat, o_lng = _parametro_float(q, 'origen_lat'), _parametro_float(q, 'origen_lng')
    d_lat, d_lng = _parametro_float(q, 'destino_lat'), _parametro_float(q, 'destino_lng')
    origen_texto = (q.get('origen_texto') or '').strip()
    destino_texto = (q.get('destino_texto') or '').strip()

    if (d_lat is None or d_lng is None) and not destino_texto:
        return Response({'detail': 'Indica la direccion de destino.'}, status=status.HTTP_400_BAD_REQUEST)

    if o_lat is not None and o_lng is not None:
        origen = {'lat': o_lat, 'lng': o_lng, 'direccion': None}
    elif origen_texto:
        origen, error = _resolver_punto(origen_texto, None, None)
        if error:
            return _error_geocodificacion(error, 'origen')
    else:
        origen = None  # hospital: Directions lo resuelve por texto

    destino, error = _resolver_punto(destino_texto, d_lat, d_lng)
    if error:
        return _error_geocodificacion(error, 'destino')

    origen_directions = f"{origen['lat']},{origen['lng']}" if origen else DESTINO_UNICO
    try:
        resp = requests.get(
            DIRECTIONS_URL,
            params={
                'origin': origen_directions,
                'destination': f"{destino['lat']},{destino['lng']}",
                'mode': 'driving',
                'alternatives': 'true',
                'departure_time': 'now',
                'region': 'cl',
                'key': settings.GOOGLE_MAPS_API_KEY,
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return Response({'detail': 'Servicio de ruteo no disponible.'}, status=status.HTTP_502_BAD_GATEWAY)

    if data.get('status') != 'OK' or not data.get('routes'):
        return Response({'detail': 'No se encontro una ruta entre esos puntos.'}, status=status.HTTP_404_NOT_FOUND)

    rutas = []
    for r in data['routes']:
        leg = r['legs'][0]
        distancia_m = leg['distance']['value']
        # Con departure_time Google entrega la duracion con el trafico actual,
        # que es lo que va pesando el taximetro en los tics de espera.
        duracion_s = (leg.get('duration_in_traffic') or leg['duration'])['value']
        rutas.append({
            'resumen': r.get('summary') or 'Ruta',
            'distancia_m': distancia_m,
            'duracion_s': duracion_s,
            'tarifa_estimada': calcular_tarifa_estimada(distancia_m, duracion_s),
            'geometry': {
                'type': 'LineString',
                'coordinates': _decodificar_polyline(r['overview_polyline']['points']),
            },
        })

    primer_leg = data['routes'][0]['legs'][0]
    if origen is None:
        origen = {
            'lat': primer_leg['start_location']['lat'],
            'lng': primer_leg['start_location']['lng'],
            'direccion': DESTINO_UNICO,
        }
    origen['direccion'] = origen['direccion'] or primer_leg.get('start_address')
    destino['direccion'] = destino['direccion'] or primer_leg.get('end_address')

    return Response({
        'origen': origen,
        'destino': destino,
        'rutas': rutas,
        'bajada_de_bandera': BAJADA_DE_BANDERA,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def estimar_tarifa(request):
    """
    Estima cuanto deberia marcar el taximetro para un traslado desde
    'origen_lat'/'origen_lng' hasta el hospital (destino fijo de
    TaxiAsiste) -- pensado para que Central pueda responder "¿cuánto sale
    aprox?" cuando alguien llama a pedir un taxi, antes de crear la
    solicitud.

    Es una ESTIMACION: el monto real del taximetro depende del trafico del
    momento y la ruta exacta que tome el conductor.
    """
    from taxiasiste.solicitudes.models import DESTINO_UNICO

    try:
        origen_lat = float(request.query_params['origen_lat'])
        origen_lng = float(request.query_params['origen_lng'])
    except (KeyError, ValueError):
        return Response(
            {'detail': 'Se requieren origen_lat y origen_lng (numericos).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data, error = calcular_ruta_a_destino_texto(origen_lat, origen_lng, DESTINO_UNICO)
    if error == 'red':
        return Response({'detail': 'Servicio de ruteo no disponible.'}, status=status.HTTP_502_BAD_GATEWAY)
    if error:
        return Response({'detail': 'No se pudo calcular una ruta desde ese origen.'}, status=status.HTTP_404_NOT_FOUND)

    leg = data['routes'][0]['legs'][0]
    distancia_m = leg['distance']['value']
    duracion_s = leg['duration']['value']

    return Response({
        'distancia_m': distancia_m,
        'duracion_s': duracion_s,
        'tarifa_estimada': calcular_tarifa_estimada(distancia_m, duracion_s),
        'bajada_de_bandera': BAJADA_DE_BANDERA,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ruta(request):
    """Traza la ruta origen->destino usando Google Directions API. Devuelve un GeoJSON LineString."""
    try:
        origen_lat = float(request.query_params['origen_lat'])
        origen_lng = float(request.query_params['origen_lng'])
        destino_lat = float(request.query_params['destino_lat'])
        destino_lng = float(request.query_params['destino_lng'])
    except (KeyError, ValueError):
        return Response(
            {'detail': 'Se requieren origen_lat, origen_lng, destino_lat, destino_lng (numericos).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data, error = calcular_ruta(origen_lat, origen_lng, destino_lat, destino_lng)
    if error == 'red':
        return Response({'detail': 'Servicio de ruteo no disponible.'}, status=status.HTTP_502_BAD_GATEWAY)
    if error:
        return Response({'detail': 'No se pudo calcular una ruta entre esos puntos.'}, status=status.HTTP_404_NOT_FOUND)

    route = data['routes'][0]
    leg = route['legs'][0]
    coordenadas = _decodificar_polyline(route['overview_polyline']['points'])
    return Response({
        'geometry': {'type': 'LineString', 'coordinates': coordenadas},
        'distancia_m': leg['distance']['value'],
        'duracion_s': leg['duration']['value'],
    })
