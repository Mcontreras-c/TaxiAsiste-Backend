import json

from channels.generic.websocket import AsyncWebsocketConsumer


class DespachoConsumer(AsyncWebsocketConsumer):
    """Envia a Central las posiciones GPS de los moviles en tiempo real."""

    GROUP_NAME = 'despacho'

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def ubicacion_actualizada(self, event):
        await self.send(text_data=json.dumps(event['data']))
