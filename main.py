from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from core.websockets import manager

from routers import customers
from routers import technicians
from routers import routes
from routers import auth
from routers import admin


app = FastAPI(
    title="Sistema de Rutas Digitales",
    description="API para gestión digital de rutas técnicas",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4321",
        "http://127.0.0.1:4321",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    customers.router,
    prefix="/api/v1",
)

app.include_router(
    technicians.router,
    prefix="/api/v1",
)

app.include_router(
    routes.router,
    prefix="/api/v1",
)

app.include_router(
    auth.router,
    prefix="/api/v1",
)

# En main.py
app.include_router(
    admin.router,
    prefix="/api/v1"
)

@app.websocket("/ws/dashboard/{technician_id}")
async def websocket_endpoint(websocket: WebSocket, technician_id: str):
    await manager.connect(websocket, technician_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(technician_id)

@app.get("/")
async def root():
    return {
        "message": "API de Rutas Digitales funcionando"
    }