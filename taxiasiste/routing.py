from django.urls import path

from taxiasiste.moviles.consumers import DespachoConsumer

websocket_urlpatterns = [
    path('ws/despacho/', DespachoConsumer.as_asgi()),
]
