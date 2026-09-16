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


@api_view(['GET'])
@permission_classes([AllowAny])
def ping(request):
    return Response({
        'status': 'ok',
        'fecha': timezone.now().isoformat(),
    })


def geocodificar_direccion(direccion):
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
