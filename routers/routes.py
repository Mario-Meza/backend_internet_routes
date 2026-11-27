from datetime import UTC, datetime
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from core.database import (
    customers_collection,
    routes_collection,
    technicians_collection,
)
from core.security import get_current_user, require_admin
from core.websockets import manager
from schemas.route import (
    CompleteServiceRequest,
    RouteCreate,
    RouteDetailResponse,
    RouteResponse,
    RouteServiceCreate,
    RouteServiceUpdate,
    RouteStatus,
    RouteStatusUpdate,
    RouteUpdate,
    ServiceStatus,
)

router = APIRouter(
    prefix="/routes",
    tags=["Routes"],
)

# ==========================================
# AYUDAS DE ACCESO
# ==========================================

async def get_route_or_404(route_id: str) -> dict:
    """Valida el ID y devuelve la ruta, o responde 400 / 404."""
    if not ObjectId.is_valid(route_id):
        raise HTTPException(
            status_code=400,
            detail="ID de ruta inválido",
        )

    route = await routes_collection.find_one({"_id": ObjectId(route_id)})

    if not route:
        raise HTTPException(
            status_code=404,
            detail="Ruta no encontrada",
        )

    return route


def ensure_route_access(
    current_user: dict,
    route: dict,
    detail: str = "No tienes acceso a esta ruta.",
) -> None:
    """Deja pasar al admin o al técnico al que está asignada la ruta.

    Cualquier otro caso (otro técnico, rol desconocido, token sin id) -> 403.
    """
    role = current_user.get("role")

    if role == "admin":
        return

    technician_id = current_user.get("id")

    if (
        role == "technician"
        and technician_id
        and route.get("technician_id") == technician_id
    ):
        return

    raise HTTPException(status_code=403, detail=detail)


# CREAR UNA RUTA
# ==========================================

@router.post(
    "/",
    response_model=RouteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)]
)
async def create_route(route: RouteCreate):

    # ==========================================
    # 1. VALIDAR TÉCNICO
    # ==========================================

    if not ObjectId.is_valid(route.technician_id):
        raise HTTPException(
            status_code=400,
            detail="ID de técnico inválido",
        )

    technician = await technicians_collection.find_one(
        {
            "_id": ObjectId(route.technician_id),
            "active": True,
        }
    )

    if not technician:
        raise HTTPException(
            status_code=404,
            detail="Técnico no encontrado o inactivo",
        )


    # ==========================================
    # 2. VALIDAR CLIENTES
    # ==========================================

    customer_ids = [
        service.customer_id
        for service in route.services
    ]


    invalid_customer_ids = [
        customer_id
        for customer_id in customer_ids
        if not ObjectId.is_valid(customer_id)
    ]


    if invalid_customer_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Uno o más IDs de clientes son inválidos",
                "customer_ids": invalid_customer_ids,
            },
        )


    customer_object_ids = [
        ObjectId(customer_id)
        for customer_id in customer_ids
    ]

    customers = []

    async for customer in customers_collection.find({
        "_id": { "$in": customer_object_ids },
        "active": {"$ne": False},
    }):
        customers.append(customer)


    found_customer_ids = {
        str(customer["_id"])
        for customer in customers
    }


    missing_customer_ids = [
        customer_id
        for customer_id in customer_ids
        if customer_id not in found_customer_ids
    ]


    if missing_customer_ids:

        raise HTTPException(
            status_code=404,
            detail={
                "message": "Uno o más clientes no fueron encontrados",
                "customer_ids": missing_customer_ids,
            },
        )


    # ==========================================
    # 3. CONSTRUIR SERVICIOS
    # ==========================================

    services = []

    for service in route.services:

        services.append(
            {
                "service_id": str(uuid4()),
                "customer_id": service.customer_id,
                "service_type": service.service_type.value,
                "status": ServiceStatus.PENDING.value,
                "notes": None,
                "started_at": None,
                "completed_at": None,
            }
        )


    # ==========================================
    # 4. CONSTRUIR RUTA
    # ==========================================

    now = datetime.now(UTC)

    route_data = {
        "route_date": route.route_date.isoformat(),
        "technician_id": route.technician_id,
        "status": RouteStatus.ASSIGNED.value,
        "services": services,
        "created_at": now,
        "updated_at": now,
    }

    result = await routes_collection.insert_one(
        route_data
    )

    # ==========================================
    # 5. NOTIFICAR AL TÉCNICO EN TIEMPO REAL
    # ==========================================

    await manager.notify_technician(
        technician_id=route.technician_id,
        message={
            "event": "NEW_ROUTE_ASSIGNED",
            "route_detail": {
                "id": str(result.inserted_id),
                "date": route.route_date.isoformat(),
                "status": RouteStatus.ASSIGNED.value
            }
        }
    )

    return RouteResponse(
        id=str(result.inserted_id),
        route_date=route.route_date,
        technician_id=route.technician_id,
        status=RouteStatus.ASSIGNED,
        services=services,
    )

# ==========================================
# CONSULTAR UNA RUTA
# ==========================================

@router.get("/{route_id}", response_model=RouteDetailResponse)
async def get_route(
    route_id: str,
    current_user: dict = Depends(get_current_user),
):
    route = await get_route_or_404(route_id)
    ensure_route_access(current_user, route)
    return await build_route_response(route)


async def build_route_response(route: dict) -> RouteDetailResponse:
    """Arma el detalle de la ruta con los datos del técnico y de cada cliente."""

    # ==========================================
    # BUSCAR TÉCNICO
    # ==========================================

    technician_id = route["technician_id"]


    if not ObjectId.is_valid(technician_id):
        raise HTTPException(
            status_code=500,
            detail="La ruta contiene un ID de técnico inválido",
        )


    technician = await technicians_collection.find_one(
        {
            "_id": ObjectId(technician_id)
        }
    )


    if not technician:
        raise HTTPException(
            status_code=404,
            detail="El técnico de la ruta no fue encontrado",
        )


    # ==========================================
    # BUSCAR CLIENTES
    # ==========================================

    route_services = route.get("services", [])


    customer_ids = [
        service["customer_id"]
        for service in route_services
        if ObjectId.is_valid(service["customer_id"])
    ]


    customer_object_ids = [
        ObjectId(customer_id)
        for customer_id in customer_ids
    ]


    customers_map = {}


    if customer_object_ids:

        async for customer in customers_collection.find(
            {
                "_id": {
                    "$in": customer_object_ids
                }
            }
        ):

            customers_map[str(customer["_id"])] = {
                "id": str(customer["_id"]),
                "name": customer["name"],
                "phone": customer["phone"],
                "location": customer["location"],
                "reference": customer.get("reference"),
            }


    # ==========================================
    # CONSTRUIR SERVICIOS
    # ==========================================

    services = []


    for service in route_services:

        customer_id = service["customer_id"]


        services.append(
            {
                "service_id": service["service_id"],
                "customer_id": customer_id,

                "customer": customers_map.get(
                    customer_id
                ),

                "service_type": service["service_type"],
                "status": service["status"],

                "notes": service.get("notes"),

                "started_at": service.get(
                    "started_at"
                ),

                "completed_at": service.get(
                    "completed_at"
                ),
            }
        )


    # ==========================================
    # RESPUESTA
    # ==========================================

    return RouteDetailResponse(
        id=str(route["_id"]),

        route_date=route["route_date"],

        technician_id=technician_id,

        technician=
        {
            "id": str(technician["_id"]),
            "name": technician["name"],
            "phone": technician.get("phone"),
            "active": technician.get("active", True),
        },

        status=route["status"],

        services=services,
    )

@router.get("/", response_model=list[RouteResponse])
async def get_routes(current_user: dict = Depends(get_current_user)):
    routes = []

    # El admin ve todas; el técnico solo las rutas que tiene asignadas.
    query: dict = {}

    if current_user.get("role") != "admin":
        technician_id = current_user.get("id")

        if current_user.get("role") != "technician" or not technician_id:
            raise HTTPException(
                status_code=403,
                detail="No tienes acceso a las rutas.",
            )

        query = {"technician_id": technician_id}

    async for route in routes_collection.find(query).sort("route_date", -1):
        routes.append(
            RouteResponse(
                id=str(route["_id"]),
                route_date=route["route_date"],
                technician_id=route["technician_id"],
                status=route["status"],
                services=route.get("services", []),
            )
        )
    return routes

# ==========================================
# ACTUALIZAR UNA RUTA
# ==========================================

@router.put(
    "/{route_id}",
    response_model=RouteResponse,
    dependencies=[Depends(require_admin)]
)
async def update_route(
    route_id: str,
    data: RouteUpdate,
):
    # ==========================================
    # VALIDAR ID
    # ==========================================

    if not ObjectId.is_valid(route_id):
        raise HTTPException(
            status_code=400,
            detail="ID de ruta inválido",
        )

    route_object_id = ObjectId(route_id)

    # ==========================================
    # BUSCAR RUTA
    # ==========================================

    route = await routes_collection.find_one(
        {"_id": route_object_id}
    )

    if not route:
        raise HTTPException(
            status_code=404,
            detail="Ruta no encontrada",
        )
    # ==========================================
    # VALIDAR ESTADO DE LA RUTA
    # ==========================================

    if route["status"] != RouteStatus.ASSIGNED.value:
        raise HTTPException(
            status_code=400,
            detail=(
                "Solo se pueden editar rutas "
                "que estén en estado assigned."
            ),
        )

    update_data = {}
    # ==========================================
    # ACTUALIZAR FECHA
    # ==========================================

    if data.route_date is not None:

        update_data["route_date"] = (
            data.route_date.isoformat()
        )

    # ==========================================
    # ACTUALIZAR TÉCNICO
    # ==========================================

    if data.technician_id is not None:

        if not ObjectId.is_valid(
            data.technician_id
        ):
            raise HTTPException(
                status_code=400,
                detail="ID de técnico inválido",
            )

        technician = (
            await technicians_collection.find_one(
                {
                    "_id": ObjectId(
                        data.technician_id
                    ),
                    "active": True,
                }
            )
        )

        if not technician:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Técnico no encontrado "
                    "o inactivo"
                ),
            )

        update_data["technician_id"] = (
            data.technician_id
        )

    # ==========================================
    # VERIFICAR QUE HAYA ALGO QUE ACTUALIZAR
    # ==========================================

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No se proporcionaron datos para actualizar.",
        )

    update_data["updated_at"] = (
        datetime.now(UTC)
    )

    # ==========================================
    # ACTUALIZAR
    # ==========================================

    result = await routes_collection.update_one(
        {"_id": route_object_id},
        {"$set": update_data},
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No se pudo actualizar la ruta.",
        )

    # ==========================================
    # OBTENER RUTA ACTUALIZADA
    # ==========================================

    updated_route = (
        await routes_collection.find_one(
            {"_id": route_object_id}
        )
    )

    return RouteResponse(
        id=str(updated_route["_id"]),
        route_date=updated_route["route_date"],
        technician_id=updated_route["technician_id"],
        status=updated_route["status"],
        services=updated_route.get(
            "services",
            []
        ),
    )
# ==========================================
# ACTUALIZAR ESTADO DE UNA RUTA
# ==========================================

@router.patch("/{route_id}/status", response_model=RouteResponse)
async def update_route_status(
    route_id: str,
    data: RouteStatusUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Actualiza el estado de una ruta y aplica las reglas de transición."""
    route = await get_route_or_404(route_id)
    ensure_route_access(
        current_user,
        route,
        detail="No puedes modificar la ruta de otro técnico.",
    )

    # Solo la oficina (admin) puede cancelar una ruta.
    if (
        current_user.get("role") != "admin"
        and data.status == RouteStatus.CANCELED
    ):
        raise HTTPException(
            status_code=403,
            detail="Solo la oficina puede cancelar una ruta.",
        )

    route_object_id = route["_id"]
    current_status = route["status"]
    new_status = data.status.value

    # Repetir la cancelación también corrige servicios antiguos que hayan
    # quedado pendientes por la versión anterior del endpoint.
    if current_status == new_status:
        if new_status == RouteStatus.CANCELED.value:
            await routes_collection.update_one(
                {
                    "_id": route_object_id,
                    "status": RouteStatus.CANCELED.value,
                },
                {
                    "$set": {
                        "services.$[service].status": ServiceStatus.CANCELED.value,
                    }
                },
                array_filters=[
                    {
                        "service.status": {
                            "$in": [
                                ServiceStatus.PENDING.value,
                                ServiceStatus.IN_PROGRESS.value,
                            ]
                        }
                    }
                ],
            )
            route = await routes_collection.find_one({"_id": route_object_id})

        return RouteResponse(
            id=str(route["_id"]),
            route_date=route["route_date"],
            technician_id=route["technician_id"],
            status=route["status"],
            services=route.get("services", []),
        )

    # Las rutas terminales no pueden reactivarse ni modificarse.
    if current_status in {
        RouteStatus.COMPLETED.value,
        RouteStatus.CANCELED.value,
    }:
        raise HTTPException(
            status_code=409,
            detail="Una ruta completada o cancelada no puede cambiar de estado.",
        )

    now = datetime.now(UTC)

    # ASSIGNED -> IN_PROGRESS
    if (
        current_status == RouteStatus.ASSIGNED.value
        and new_status == RouteStatus.IN_PROGRESS.value
    ):
        result = await routes_collection.update_one(
            {
                "_id": route_object_id,
                "status": RouteStatus.ASSIGNED.value,
            },
            {
                "$set": {
                    "status": RouteStatus.IN_PROGRESS.value,
                    "updated_at": now,
                }
            },
        )

    # ASSIGNED / IN_PROGRESS -> CANCELED.
    # Los servicios pendientes o en proceso se cancelan; los completados se conservan.
    elif (
        new_status == RouteStatus.CANCELED.value
        and current_status in {
            RouteStatus.ASSIGNED.value,
            RouteStatus.IN_PROGRESS.value,
        }
    ):
        result = await routes_collection.update_one(
            {
                "_id": route_object_id,
                "status": current_status,
            },
            {
                "$set": {
                    "status": RouteStatus.CANCELED.value,
                    "updated_at": now,
                    "services.$[service].status": ServiceStatus.CANCELED.value,
                }
            },
            array_filters=[
                {
                    "service.status": {
                        "$in": [
                            ServiceStatus.PENDING.value,
                            ServiceStatus.IN_PROGRESS.value,
                        ]
                    }
                }
            ],
        )

    # IN_PROGRESS -> COMPLETED only when every service is completed.
    elif (
        current_status == RouteStatus.IN_PROGRESS.value
        and new_status == RouteStatus.COMPLETED.value
    ):
        services = route.get("services", [])
        if not services:
            raise HTTPException(
                status_code=409,
                detail="La ruta no tiene servicios y no se puede completar.",
            )

        if not all(
            service.get("status") == ServiceStatus.COMPLETED.value
            for service in services
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "No se puede completar la ruta porque todavía existen "
                    "servicios pendientes, en proceso o cancelados."
                ),
            )

        result = await routes_collection.update_one(
            {
                "_id": route_object_id,
                "status": RouteStatus.IN_PROGRESS.value,
            },
            {
                "$set": {
                    "status": RouteStatus.COMPLETED.value,
                    "updated_at": now,
                }
            },
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No se permite cambiar la ruta de '{current_status}' "
                f"a '{new_status}'."
            ),
        )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "La ruta cambió mientras se procesaba la solicitud. "
                "Recarga la página e inténtalo de nuevo."
            ),
        )

    updated_route = await routes_collection.find_one({"_id": route_object_id})
    if not updated_route:
        raise HTTPException(
            status_code=404,
            detail="Ruta no encontrada después de actualizarla.",
        )

    # ---> AGREGAR ESTO: NOTIFICAR CANCELACIÓN DE RUTA <---
    if new_status == RouteStatus.CANCELED.value:
        await manager.notify_technician(
            technician_id=updated_route["technician_id"],
            message={
                "event": "ROUTE_CANCELED",
                "route_detail": {
                    "id": str(updated_route["_id"])
                }
            }
        )

    return RouteResponse(
        id=str(updated_route["_id"]),
        route_date=updated_route["route_date"],
        technician_id=updated_route["technician_id"],
        status=updated_route["status"],
        services=updated_route.get("services", []),
    )

# ==========================================
# ELIMINAR UNA RUTA
# ==========================================

@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_route(route_id: str):
    # ==========================================
    # VALIDAR ID
    # ==========================================

    if not ObjectId.is_valid(route_id):
        raise HTTPException(
            status_code=400,
            detail="ID de ruta inválido",
        )

    route_object_id = ObjectId(route_id)

    # ==========================================
    # BUSCAR RUTA
    # ==========================================

    route = await routes_collection.find_one(
        {"_id": route_object_id}
    )

    if not route:
        raise HTTPException(
            status_code=404,
            detail="Ruta no encontrada",
        )

    # ==========================================
    # VALIDAR ESTADO
    # ==========================================

    if route["status"] != RouteStatus.ASSIGNED.value:
        raise HTTPException(
            status_code=409,
            detail=(
                "Solo se pueden eliminar rutas asignadas. "
                "Las rutas en proceso, completadas o canceladas "
                "se conservan como historial."
            ),
        )

    # ==========================================
    # ELIMINAR
    # ==========================================

    technician_id_to_notify = route["technician_id"]

    result = await routes_collection.delete_one(
        {"_id": route_object_id}
    )

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="No se pudo eliminar la ruta.",
        )

    await manager.notify_technician(
        technician_id=technician_id_to_notify,
        message={
            "event": "ROUTE_DELETED",
            "route_detail": {
                "id": str(route_object_id)
            }
        }
    )
    # ---> FIN DEL BLOQUE AGREGADO <---

    return None


@router.post(
    "/{route_id}/services",
    response_model=RouteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)]
)

async def add_route_service(
        route_id: str,
        service: RouteServiceCreate,
):
    # ==========================================
    # 1. VALIDAR ID DE RUTA
    # ==========================================
    if not ObjectId.is_valid(route_id):

        raise HTTPException(
            status_code=400,
            detail="ID de ruta inválido",
        )
    # ==========================================
    # 2. BUSCAR RUTA
    # ==========================================

    route = await routes_collection.find_one(
        {
            "_id": ObjectId(route_id)
        }
    )


    if not route:

        raise HTTPException(
            status_code=404,
            detail="Ruta no encontrada",
        )
    # ==========================================
    # 3. SOLO SE PUEDE EDITAR UNA RUTA ASIGNADA
    # ==========================================

    if route.get("status") != RouteStatus.ASSIGNED.value:

        raise HTTPException(
            status_code=409,
            detail="Solo se pueden agregar servicios a una ruta asignada.",
        )
    # ==========================================
    # 4. VALIDAR CLIENTE
    # ==========================================

    if not ObjectId.is_valid(
        service.customer_id
    ):

        raise HTTPException(
            status_code=400,
            detail="ID de cliente inválido",
        )


    customer = await customers_collection.find_one(
        {
            "_id": ObjectId(service.customer_id),
            "active": True,
        }
    )


    if not customer:

        raise HTTPException(
            status_code=404,
            detail="Cliente no encontrado o inactivo",
        )
    # ==========================================
    # 5. CONSTRUIR SERVICIO
    # ==========================================

    new_service = {

        "service_id":
            str(uuid4()),

        "customer_id":
            service.customer_id,

        "service_type":
            service.service_type.value,

        "status":
            ServiceStatus.PENDING.value,

        "notes":
            None,

        "started_at":
            None,

        "completed_at":
            None,
    }

    # ==========================================
    # 6. AGREGAR SERVICIO
    # ==========================================

    result = await routes_collection.update_one(

        {
            "_id":
                ObjectId(route_id),

            "status":
                RouteStatus.ASSIGNED.value,
        },

        {
            "$push":
                {
                    "services":
                        new_service,
                },

            "$set":
                {
                    "updated_at":
                        datetime.now(UTC),
                },
        },
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=409,
            detail="No se pudo agregar el servicio.",
        )

    # ==========================================
    # 7. OBTENER RUTA ACTUALIZADA
    # ==========================================

    updated_route = await routes_collection.find_one(
            {
                "_id":
                    ObjectId(route_id)
            }
        )

    # ==========================================
    # 7. OBTENER RUTA ACTUALIZADA
    # ==========================================

    updated_route = await routes_collection.find_one(
        {
            "_id":
                ObjectId(route_id)
        }
    )

    # ---> AGREGAR ESTO: NOTIFICAR AL TÉCNICO <---
    await manager.notify_technician(
        technician_id=updated_route["technician_id"],
        message={
            "event": "NEW_SERVICE_ADDED",
            "route_detail": {
                "id": str(updated_route["_id"]),
                "status": updated_route["status"]
            }
        }
    )
    # ---> FIN DEL BLOQUE AGREGADO <---


    return RouteResponse(
        id = str(
            updated_route["_id"]
        ),

        route_date=
            updated_route["route_date"],

        technician_id=
            updated_route["technician_id"],

        status=
            updated_route["status"],

        services=
            updated_route.get(
                "services",
                [],
            ),
    )


#==========================================
# INICIAR UN SERVICIO EN UNA RUTA
#==========================================
@router.patch(
    "/{route_id}/services/{service_id}/start",
    response_model=RouteResponse,
)
async def start_service(
    route_id: str,
    service_id: str,
    current_user: dict = Depends(get_current_user),
):
    route = await get_route_or_404(route_id)
    ensure_route_access(
        current_user,
        route,
        detail="Esta ruta pertenece a otro técnico.",
    )
    route_object_id = route["_id"]

    if route.get("status") not in {
        RouteStatus.ASSIGNED.value,
        RouteStatus.IN_PROGRESS.value,
    }:
        raise HTTPException(
            status_code=409,
            detail="No se pueden iniciar servicios en una ruta completada o cancelada.",
        )

    service_exists = any(
        service.get("service_id") == service_id
        for service in route.get("services", [])
    )
    if not service_exists:
        raise HTTPException(
            status_code=404,
            detail="Servicio no encontrado",
        )

    now = datetime.now(UTC)
    result = await routes_collection.update_one(
        {
            "_id": route_object_id,
            "status": {
                "$in": [
                    RouteStatus.ASSIGNED.value,
                    RouteStatus.IN_PROGRESS.value,
                ]
            },
            "services": {
                "$elemMatch": {
                    "service_id": service_id,
                    "status": ServiceStatus.PENDING.value,
                }
            },
        },
        {
            "$set": {
                "services.$.status": ServiceStatus.IN_PROGRESS.value,
                "services.$.started_at": now,
                "status": RouteStatus.IN_PROGRESS.value,
                "updated_at": now,
            }
        },
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "El servicio ya no está pendiente o la ruta dejó de estar activa. "
                "Actualiza la página."
            ),
        )

    updated_route = await routes_collection.find_one({"_id": route_object_id})
    return RouteResponse(
        id=str(updated_route["_id"]),
        route_date=updated_route["route_date"],
        technician_id=updated_route["technician_id"],
        status=updated_route["status"],
        services=updated_route.get("services", []),
    )

#==========================================
# COMPLETAR UN SERVICIO EN UNA RUTA
#==========================================
@router.patch(
    "/{route_id}/services/{service_id}/complete",
    response_model=RouteResponse,
)
async def complete_service(
    route_id: str,
    service_id: str,
    data: CompleteServiceRequest | None = None,
    current_user: dict = Depends(get_current_user),
):
    route = await get_route_or_404(route_id)
    ensure_route_access(
        current_user,
        route,
        detail="Esta ruta pertenece a otro técnico.",
    )
    route_object_id = route["_id"]
    notes = data.notes if data else None

    if route.get("status") != RouteStatus.IN_PROGRESS.value:
        raise HTTPException(
            status_code=409,
            detail="Solo se pueden completar servicios de una ruta en proceso.",
        )

    service_exists = any(
        service.get("service_id") == service_id
        for service in route.get("services", [])
    )
    if not service_exists:
        raise HTTPException(
            status_code=404,
            detail="Servicio no encontrado",
        )

    now = datetime.now(UTC)
    result = await routes_collection.update_one(
        {
            "_id": route_object_id,
            "status": RouteStatus.IN_PROGRESS.value,
            "services": {
                "$elemMatch": {
                    "service_id": service_id,
                    "status": ServiceStatus.IN_PROGRESS.value,
                }
            },
        },
        {
            "$set": {
                "services.$.status": ServiceStatus.COMPLETED.value,
                "services.$.completed_at": now,
                "services.$.notes": notes,
                "updated_at": now,
            }
        },
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "El servicio debe estar en proceso y la ruta debe seguir activa "
                "para poder completarlo."
            ),
        )

    updated_route = await routes_collection.find_one({"_id": route_object_id})
    services = updated_route.get("services", [])
    all_completed = bool(services) and all(
        service.get("status") == ServiceStatus.COMPLETED.value
        for service in services
    )

    # No sobrescribir una cancelación que ocurra concurrentemente.
    if all_completed:
        await routes_collection.update_one(
            {
                "_id": route_object_id,
                "status": RouteStatus.IN_PROGRESS.value,
            },
            {
                "$set": {
                    "status": RouteStatus.COMPLETED.value,
                    "updated_at": datetime.now(UTC),
                }
            },
        )

    updated_route = await routes_collection.find_one({"_id": route_object_id})
    return RouteResponse(
        id=str(updated_route["_id"]),
        route_date=updated_route["route_date"],
        technician_id=updated_route["technician_id"],
        status=updated_route["status"],
        services=updated_route.get("services", []),
    )

# ==========================================
# ACTUALIZAR UN SERVICIO DE UNA RUTA
# ==========================================

@router.put(
    "/{route_id}/services/{service_id}",
    response_model=RouteResponse,
    dependencies=[Depends(require_admin)]
)
async def update_route_service(
    route_id: str,
    service_id: str,
    data: RouteServiceUpdate,
):

    # ==========================================
    # VALIDAR ID DE RUTA
    # ==========================================

    if not ObjectId.is_valid(route_id):
        raise HTTPException(
            status_code=400,
            detail="ID de ruta inválido",
        )

    route_object_id = ObjectId(route_id)

    # ==========================================
    # BUSCAR RUTA
    # ==========================================

    route = await routes_collection.find_one(
        {"_id": route_object_id}
    )

    if not route:
        raise HTTPException(
            status_code=404,
            detail="Ruta no encontrada",
        )

    # ==========================================
    # VALIDAR ESTADO DE LA RUTA
    # ==========================================

    if route["status"] != RouteStatus.ASSIGNED.value:
        raise HTTPException(
            status_code=400,
            detail=(
                "Solo se pueden editar servicios "
                "de rutas que estén en estado assigned."
            ),
        )

    # ==========================================
    # BUSCAR SERVICIO
    # ==========================================

    service = next(
        (
            item
            for item in route.get("services", [])
            if item.get("service_id") == service_id
        ),
        None,
    )

    if not service:
        raise HTTPException(
            status_code=404,
            detail="Servicio no encontrado",
        )

    # ==========================================
    # VALIDAR ESTADO DEL SERVICIO
    # ==========================================

    if service["status"] != ServiceStatus.PENDING.value:
        raise HTTPException(
            status_code=400,
            detail=(
                "Solo se pueden editar servicios "
                "que estén pendientes."
            ),
        )

    # ==========================================
    # CONSTRUIR CAMBIOS
    # ==========================================

    update_fields = {}

    # ------------------------------------------
    # ACTUALIZAR CLIENTE
    # ------------------------------------------

    if data.customer_id is not None:

        if not ObjectId.is_valid(data.customer_id):
            raise HTTPException(
                status_code=400,
                detail="ID de cliente inválido",
            )

        customer = await customers_collection.find_one(
            {
                "_id": ObjectId(data.customer_id),
            }
        )

        if not customer:
            raise HTTPException(
                status_code=404,
                detail="Cliente no encontrado",
            )

        update_fields[
            "services.$.customer_id"
        ] = data.customer_id

    # ------------------------------------------
    # ACTUALIZAR TIPO DE SERVICIO
    # ------------------------------------------

    if data.service_type is not None:

        update_fields[
            "services.$.service_type"
        ] = data.service_type.value

    # ==========================================
    # VERIFICAR QUE HAYA CAMBIOS
    # ==========================================

    if not update_fields:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se proporcionaron datos "
                "para actualizar."
            ),
        )

    update_fields[
        "updated_at"
    ] = datetime.now(UTC)

    # ==========================================
    # ACTUALIZAR SERVICIO
    # ==========================================

    result = await routes_collection.update_one(
        {
            "_id": route_object_id,
            "services.service_id": service_id,
        },
        {
            "$set": update_fields,
        },
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No se pudo actualizar el servicio.",
        )

    # ==========================================
    # OBTENER RUTA ACTUALIZADA
    # ==========================================

    updated_route = await routes_collection.find_one(
        {"_id": route_object_id}
    )

    return RouteResponse(
        id=str(updated_route["_id"]),
        route_date=updated_route["route_date"],
        technician_id=updated_route["technician_id"],
        status=updated_route["status"],
        services=updated_route.get(
            "services",
            [],
        ),
    )

# ==========================================
# ELIMINAR UN SERVICIO DE UNA RUTA
# ==========================================

@router.delete("/{route_id}/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_route_service(route_id: str, service_id: str):
    # ==========================================
    # VALIDAR ID DE RUTA
    # ==========================================

    if not ObjectId.is_valid(route_id):
        raise HTTPException(
            status_code=400,
            detail="ID de ruta inválido",
        )

    route_object_id = ObjectId(route_id)

    # ==========================================
    # BUSCAR RUTA
    # ==========================================

    route = await routes_collection.find_one(
        {"_id": route_object_id}
    )

    if not route:
        raise HTTPException(
            status_code=404,
            detail="Ruta no encontrada",
        )

    # ==========================================
    # VALIDAR ESTADO DE LA RUTA
    # ==========================================

    if route["status"] != RouteStatus.ASSIGNED.value:
        raise HTTPException(
            status_code=400,
            detail=(
                "Solo se pueden eliminar servicios "
                "de rutas que estén en estado assigned."
            ),
        )

    # ==========================================
    # BUSCAR SERVICIO
    # ==========================================

    services = route.get("services", [])

    service = next(
        (
            item
            for item in services
            if item.get("service_id") == service_id
        ),
        None,
    )

    if not service:
        raise HTTPException(
            status_code=404,
            detail="Servicio no encontrado",
        )

    # ==========================================
    # VALIDAR ESTADO DEL SERVICIO
    # ==========================================

    if service["status"] != ServiceStatus.PENDING.value:
        raise HTTPException(
            status_code=400,
            detail=(
                "Solo se pueden eliminar servicios "
                "que estén pendientes."
            ),
        )

    # ==========================================
    # EVITAR RUTAS SIN SERVICIOS
    # ==========================================

    if len(services) <= 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se puede eliminar el último "
                "servicio de la ruta."
            ),
        )

    # ==========================================
    # ELIMINAR SERVICIO
    # ==========================================

    result = await routes_collection.update_one(
        {
            "_id": route_object_id,
        },
        {
            "$pull": {
                "services": {
                    "service_id": service_id,
                },
            },
            "$set": {
                "updated_at": datetime.now(
                    UTC
                ),
            },
        },
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No se pudo eliminar el servicio.",
        )

    await manager.notify_technician(
        technician_id=route["technician_id"],
        message={
            "event": "SERVICE_DELETED",
            "route_detail": {
                "id": str(route_object_id),
                "service_id": service_id
            }
        }
    )

    return None