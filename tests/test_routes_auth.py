# tests/test_routes_auth.py
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import core.security as security_module
import routers.routes as routes_module
from core.security import create_access_token
from main import app

TECH_A_ID = str(ObjectId())
TECH_B_ID = str(ObjectId())
ROUTE_ID = str(ObjectId())
CUSTOMER_ID = str(ObjectId())


class FakeCursor:
    """Simula un cursor asíncrono de PyMongo con soporte para .sort()."""

    def __init__(self, items: list[dict]):
        self._items = items

    def sort(self, *_args, **_kwargs):
        return self

    def __aiter__(self):
        self._iter = iter(self._items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


def make_auth_headers(role: str, user_id: str | None = None) -> dict[str, str]:
    payload: dict[str, str] = {"sub": f"{role}@rutas.test", "role": role}
    if user_id:
        payload["id"] = user_id
    token = create_access_token(payload)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


# ==========================================
# 1. ENDPOINTS PROTEGIDOS SIN SESIÓN
# ==========================================


@pytest.mark.parametrize(
    ("method", "url", "kwargs"),
    [
        ("DELETE", f"/api/v1/technicians/{TECH_A_ID}", {}),
        ("PATCH", f"/api/v1/technicians/{TECH_A_ID}/active", {"json": {"active": False}}),
        ("GET", f"/api/v1/technicians/{TECH_A_ID}", {}),
        (
            "POST",
            f"/api/v1/technicians/{TECH_A_ID}/photo",
            {"files": {"file": ("photo.jpg", b"fake-image", "image/jpeg")}},
        ),
        ("DELETE", f"/api/v1/technicians/{TECH_A_ID}/photo", {}),
        ("PATCH", f"/api/v1/customers/{CUSTOMER_ID}/active", {"json": {"active": False}}),
        ("GET", "/api/v1/routes/", {}),
        ("PATCH", f"/api/v1/routes/{ROUTE_ID}/services/srv-1/start", {}),
        ("PATCH", f"/api/v1/routes/{ROUTE_ID}/services/srv-1/complete", {"json": {"notes": "ok"}}),
    ],
)
async def test_protected_endpoints_reject_unauthenticated_requests(
    client: AsyncClient,
    method: str,
    url: str,
    kwargs: dict,
):
    response = await client.request(method, url, **kwargs)
    assert response.status_code in (401, 403)


# ==========================================
# 2. CONTROL DE ROL (SOLO ADMIN)
# ==========================================


@pytest.mark.parametrize(
    ("method", "url", "kwargs"),
    [
        ("DELETE", f"/api/v1/technicians/{TECH_B_ID}", {}),
        ("PATCH", f"/api/v1/technicians/{TECH_B_ID}/active", {"json": {"active": False}}),
        ("PATCH", f"/api/v1/customers/{CUSTOMER_ID}/active", {"json": {"active": False}}),
        ("DELETE", f"/api/v1/routes/{ROUTE_ID}", {}),
        (
            "POST",
            "/api/v1/customers/",
            {
                "json": {
                    "name": "Cliente Prueba",
                    "phone": "+525512345678",
                    "location": "Centro",
                }
            },
        ),
    ],
)
async def test_technician_cannot_access_admin_endpoints(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    url: str,
    kwargs: dict,
):
    monkeypatch.setattr(
        security_module.technicians_collection,
        "find_one",
        AsyncMock(return_value={"_id": ObjectId(TECH_A_ID), "active": True}),
    )

    headers = make_auth_headers("technician", TECH_A_ID)
    response = await client.request(method, url, headers=headers, **kwargs)
    assert response.status_code == 403


# ==========================================
# 3. TÉCNICO DESACTIVADO CON TOKEN VIGENTE
# ==========================================


async def test_inactive_technician_token_is_rejected(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        security_module.technicians_collection,
        "find_one",
        AsyncMock(return_value={"_id": ObjectId(TECH_A_ID), "active": False}),
    )

    headers = make_auth_headers("technician", TECH_A_ID)
    response = await client.get("/api/v1/routes/", headers=headers)
    assert response.status_code == 401


# ==========================================
# 4. PROPIEDAD DE RUTA Y CANCELACIÓN
# ==========================================


@pytest.mark.parametrize(
    ("method", "url", "kwargs"),
    [
        ("GET", f"/api/v1/routes/{ROUTE_ID}", {}),
        ("PATCH", f"/api/v1/routes/{ROUTE_ID}/status", {"json": {"status": "in_progress"}}),
        ("PATCH", f"/api/v1/routes/{ROUTE_ID}/services/srv-1/start", {}),
        ("PATCH", f"/api/v1/routes/{ROUTE_ID}/services/srv-1/complete", {"json": {"notes": "ok"}}),
    ],
)
async def test_technician_cannot_touch_another_technicians_route(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    url: str,
    kwargs: dict,
):
    monkeypatch.setattr(
        security_module.technicians_collection,
        "find_one",
        AsyncMock(return_value={"_id": ObjectId(TECH_A_ID), "active": True}),
    )
    monkeypatch.setattr(
        routes_module.routes_collection,
        "find_one",
        AsyncMock(
            return_value={
                "_id": ObjectId(ROUTE_ID),
                "route_date": "2026-11-27",
                "technician_id": TECH_B_ID,
                "status": "assigned",
                "services": [],
            }
        ),
    )

    headers = make_auth_headers("technician", TECH_A_ID)
    response = await client.request(method, url, headers=headers, **kwargs)
    assert response.status_code == 403


async def test_technician_cannot_cancel_own_route(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        security_module.technicians_collection,
        "find_one",
        AsyncMock(return_value={"_id": ObjectId(TECH_A_ID), "active": True}),
    )
    monkeypatch.setattr(
        routes_module.routes_collection,
        "find_one",
        AsyncMock(
            return_value={
                "_id": ObjectId(ROUTE_ID),
                "route_date": "2026-11-27",
                "technician_id": TECH_A_ID,
                "status": "assigned",
                "services": [],
            }
        ),
    )

    headers = make_auth_headers("technician", TECH_A_ID)
    response = await client.patch(
        f"/api/v1/routes/{ROUTE_ID}/status",
        headers=headers,
        json={"status": "canceled"},
    )
    assert response.status_code == 403


# ==========================================
# 5. FILTRADO POR DUEÑO EN GET /routes/
# ==========================================


async def test_get_routes_filters_by_technician_id_and_allows_all_for_admin(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured_queries: list[dict] = []

    def fake_find(query: dict):
        captured_queries.append(query)
        return FakeCursor([])

    monkeypatch.setattr(
        security_module.technicians_collection,
        "find_one",
        AsyncMock(return_value={"_id": ObjectId(TECH_A_ID), "active": True}),
    )
    monkeypatch.setattr(routes_module.routes_collection, "find", fake_find)

    tech_response = await client.get(
        "/api/v1/routes/",
        headers=make_auth_headers("technician", TECH_A_ID),
    )
    assert tech_response.status_code == 200
    assert tech_response.json() == []

    admin_response = await client.get(
        "/api/v1/routes/",
        headers=make_auth_headers("admin"),
    )
    assert admin_response.status_code == 200
    assert admin_response.json() == []

    assert captured_queries == [{"technician_id": TECH_A_ID}, {}]