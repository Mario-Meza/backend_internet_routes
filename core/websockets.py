# core/websockets.py
import logging
from fastapi import WebSocket

logger = logging.getLogger("rutas_digitales.websockets")


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, technician_id: str) -> None:
        await websocket.accept()
        self.active_connections[technician_id] = websocket
        logger.info("WebSocket conectado para técnico %s", technician_id)

    def disconnect(self, technician_id: str) -> None:
        if technician_id in self.active_connections:
            del self.active_connections[technician_id]
            logger.info("WebSocket desconectado para técnico %s", technician_id)

    async def notify_technician(self, technician_id: str, message: dict) -> None:
        websocket = self.active_connections.get(technician_id)
        if not websocket:
            return
        try:
            await websocket.send_json(message)
        except Exception as exc:
            logger.warning(
                "Error enviando mensaje WS al técnico %s: %s",
                technician_id,
                exc,
            )
            self.disconnect(technician_id)


manager = ConnectionManager()