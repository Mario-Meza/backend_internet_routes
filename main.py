from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import customers
from routers import technicians
from routers import routes


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


@app.get("/")
async def root():
    return {
        "message": "API de Rutas Digitales funcionando"
    }