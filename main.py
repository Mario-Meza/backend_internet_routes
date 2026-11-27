from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import technicians_collection
from core.security import decode_access_token, verify_active_user
from core.websockets import manager
from routers import admin, auth, customers, routes, technicians


@asynccontextmanager
async def lifespan(app: FastAPI):
    await technicians_collection.create_index("email", unique=True)
    yield

app = FastAPI(title="Rutas Digitales API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(technicians.router, prefix="/api/v1")
app.include_router(customers.router, prefix="/api/v1")
app.include_router(routes.router, prefix="/api/v1")

@app.websocket("/ws/dashboard/{technician_id}")
async def websocket_dashboard(
    websocket: WebSocket,
    technician_id: str,
    token: str | None = Query(default=None),
):
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:

        payload = decode_access_token(token)
        await verify_active_user(payload)
        token_tech_id = payload.get("id") or payload.get("_id") or payload.get("user_id")
        role = payload.get("role")

        # Validar que sea técnico y que el ID del token coincida con la URL
        if role != "technician" or str(token_tech_id) != str(technician_id):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, technician_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(technician_id)