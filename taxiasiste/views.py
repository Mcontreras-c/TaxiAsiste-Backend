import re
import time

import requests
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

# Nominatim exige un User-Agent identificable y max ~1 request/segundo — un
# navegador no puede fijar el header User-Agent via fetch/axios, por eso esto
# pasa por el backend en vez de llamarse directo desde el frontend.
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
NOMINATIM_USER_AGENT = 'TaxiAsiste/1.0 (uso interno sindicato de taxis)'

def _separar_calle_comuna(direccion):
    """'Leon XIII 2477, Maipu' -> ('Leon XIII 2477', 'Maipu'). Sin coma, todo es 'calle'."""
    partes = [p.strip() for p in direccion.split(',') if p.strip()]
    if len(partes) >= 2:
        return partes[0], partes[1]
    return partes[0] if partes else direccion.strip(), None


def _quitar_numeracion(calle):
    """'Leon XIII 2477' -> 'Leon XIII' (sin el numero de casa)."""
    sin_numero = re.sub(r'\b\d+[A-Za-z]?\b', '', calle)
    return re.sub(r'\s{2,}', ' ', sin_numero).strip(' ,')


def _tiene_calle_valida(item):
    """
    Nominatim devuelve el 'address' desglosado solo con addressdetails=1.
    Sin la clave 'road', el resultado es un barrio/suburbio/comuna generico
    (ej. 'Marianela' en vez de 'Leon XIII') — no sirve para despacho de taxis.
    """
    return bool(item.get('address', {}).get('road'))


def _consultar_nominatim_estructurado(calle, comuna):
    """Busqueda estructurada (street/city/country) en vez de 'q' libre —
    evita que Nominatim adivine mal y devuelva un barrio en vez de la calle."""
    params = {
        'street': calle,
        'country': 'Chile',
        'format': 'json',
        'limit': 1,
        'addressdetails': 1,
        'countrycodes': 'cl',
    }
    if comuna:
        params['city'] = comuna
    resp = requests.get(
        NOMINATIM_URL,
        params=params,
        headers={'User-Agent': NOMINATIM_USER_AGENT},
        timeout=6,
    )
    resp.raise_for_status()
    return resp.json()

# Servidor demo publico de OSRM — sin key, sin SLA garantizado (suficiente
# para desarrollo/piloto; para produccion con mas trafico conviene
# autoalojar el servicio).
OSRM_URL = 'https://router.project-osrm.org/route/v1/driving'


@api_view(['GET'])
@permission_classes([AllowAny])
def ping(request):
    return Response({
        'status': 'ok',
        'fecha': timezone.now().isoformat(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def geocodificar(request):
    """Convierte una direccion en texto a lat/lng usando busqueda estructurada de Nominatim (OSM)."""
    direccion = request.query_params.get('direccion', '').strip()
    if not direccion:
        return Response({'detail': 'Parametro "direccion" es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

    calle, comuna = _separar_calle_comuna(direccion)

    try:
        resultados = _consultar_nominatim_estructurado(calle, comuna)

        # Validacion estricta: sin 'road' en el address, Nominatim no ubico
        # la calle (devolvio un barrio/suburbio, ej. 'Marianela' en vez de
        # 'Leon XIII') — se reintenta solo con la calle, sin el numero,
        # que suele ser lo que le impide encontrarla.
        if not resultados or not _tiene_calle_valida(resultados[0]):
            calle_sin_numero = _quitar_numeracion(calle)
            if calle_sin_numero and calle_sin_numero != calle:
                # Nominatim exige max ~1 req/s; sin esta pausa, el segundo
                # intento (fallback) puede ser descartado/throttleado por ir
                # pegado al primero dentro de la misma request.
                time.sleep(1)
                resultados_fallback = _consultar_nominatim_estructurado(calle_sin_numero, comuna)
                if resultados_fallback:
                    resultados = resultados_fallback
    except requests.RequestException:
        return Response({'detail': 'Servicio de geocodificacion no disponible.'}, status=status.HTTP_502_BAD_GATEWAY)

    if not resultados or not _tiene_calle_valida(resultados[0]):
        return Response(
            {'detail': 'No se pudo ubicar la calle exacta de esta dirección.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    r = resultados[0]
    return Response({
        'lat': float(r['lat']),
        'lng': float(r['lon']),
        'direccion_formateada': r.get('display_name', direccion),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ruta(request):
    """Traza la ruta origen->destino usando OSRM. Devuelve un GeoJSON LineString."""
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

    coords = f'{origen_lng},{origen_lat};{destino_lng},{destino_lat}'
    try:
        resp = requests.get(
            f'{OSRM_URL}/{coords}',
            params={'overview': 'full', 'geometries': 'geojson'},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return Response({'detail': 'Servicio de ruteo no disponible.'}, status=status.HTTP_502_BAD_GATEWAY)

    if data.get('code') != 'Ok' or not data.get('routes'):
        return Response({'detail': 'No se pudo calcular una ruta entre esos puntos.'}, status=status.HTTP_404_NOT_FOUND)

    route = data['routes'][0]
    return Response({
        'geometry': route['geometry'],  # GeoJSON LineString: {type, coordinates: [[lng,lat], ...]}
        'distancia_m': route['distance'],
        'duracion_s': route['duration'],
    })
