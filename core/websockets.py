from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, technician_id: str):
        await websocket.accept()
        self.active_connections[technician_id] = websocket
        print(f"\n🟢 [WS] TÉCNICO CONECTADO: '{technician_id}'")
        print(f"👥 [WS] USUARIOS ACTIVOS: {list(self.active_connections.keys())}\n")

    def disconnect(self, technician_id: str):
        if technician_id in self.active_connections:
            del self.active_connections[technician_id]
            print(f"\n🔴 [WS] TÉCNICO DESCONECTADO: '{technician_id}'\n")

    async def notify_technician(self, technician_id: str, message: dict):
        print(f"\n🔔 [WS] INTENTANDO NOTIFICAR A: '{technician_id}'...")
        if websocket := self.active_connections.get(technician_id):
            await websocket.send_json(message)
            print(f"✅ [WS] MENSAJE ENVIADO CON ÉXITO AL TÉCNICO '{technician_id}'\n")
        else:
            print(f"❌ [WS] ERROR: EL TÉCNICO '{technician_id}' NO ESTÁ CONECTADO.\n")

manager = ConnectionManager()