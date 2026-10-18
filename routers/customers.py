from bson import ObjectId
from fastapi import APIRouter, HTTPException, status

from core.database import customers_collection, routes_collection

from schemas.customer import (
    CustomerActiveUpdate,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
)


router = APIRouter(
    prefix="/customers",
    tags=["Customers"],
)


def validate_object_id(
    customer_id: str,
) -> ObjectId:

    if not ObjectId.is_valid(customer_id):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de cliente inválido",
        )

    return ObjectId(customer_id)


def customer_to_response(
    customer: dict,
) -> CustomerResponse:

    return CustomerResponse(
        id=str(customer["_id"]),
        name=customer["name"],
        phone=customer["phone"],
        location=customer["location"],
        reference=customer.get("reference"),
        active=customer.get("active", True),
    )


# ==========================================
# CREAR CLIENTE
# ==========================================

@router.post(
    "/",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer(
    customer: CustomerCreate,
):

    customer_data = customer.model_dump()

    customer_data["active"] = True


    result = await customers_collection.insert_one(
        customer_data
    )


    created_customer = await customers_collection.find_one(
        {
            "_id": result.inserted_id
        }
    )


    return customer_to_response(
        created_customer
    )


# ==========================================
# LISTAR CLIENTES
# ==========================================

@router.get(
    "/",
    response_model=list[CustomerResponse],
)
async def get_customers():

    customers = []


    cursor = customers_collection.find().sort(
        "name",
        1,
    )


    async for customer in cursor:

        customers.append(
            customer_to_response(
                customer
            )
        )


    return customers


# ==========================================
# OBTENER CLIENTE
# ==========================================

@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
)
async def get_customer(
    customer_id: str,
):

    object_id = validate_object_id(
        customer_id
    )


    customer = await customers_collection.find_one(
        {
            "_id": object_id
        }
    )


    if not customer:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado",
        )


    return customer_to_response(
        customer
    )


# ==========================================
# ACTUALIZAR CLIENTE
# ==========================================

@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
)
async def update_customer(
    customer_id: str,
    customer: CustomerUpdate,
):

    object_id = validate_object_id(
        customer_id
    )


    existing_customer = await customers_collection.find_one(
        {
            "_id": object_id
        }
    )


    if not existing_customer:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado",
        )


    update_data = customer.model_dump(
        exclude_unset=True
    )


    if not update_data:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay datos para actualizar",
        )


    await customers_collection.update_one(
        {
            "_id": object_id
        },
        {
            "$set": update_data
        },
    )


    updated_customer = await customers_collection.find_one(
        {
            "_id": object_id
        }
    )


    return customer_to_response(
        updated_customer
    )


# ==========================================
# ACTIVAR / DESACTIVAR
# ==========================================

@router.patch(
    "/{customer_id}/active",
    response_model=CustomerResponse,
)
async def update_customer_active(
    customer_id: str,
    data: CustomerActiveUpdate,
):

    object_id = validate_object_id(
        customer_id
    )


    result = await customers_collection.update_one(
        {
            "_id": object_id
        },
        {
            "$set": {
                "active": data.active
            }
        },
    )


    if result.matched_count == 0:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado",
        )


    customer = await customers_collection.find_one(
        {
            "_id": object_id
        }
    )


    return customer_to_response(
        customer
    )


# ==========================================
# ELIMINAR CLIENTE
# ==========================================

@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_customer(
    customer_id: str,
):

    object_id = validate_object_id(
        customer_id
    )


    customer = await customers_collection.find_one(
        {
            "_id": object_id
        }
    )


    if not customer:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado",
        )


    # ==========================================
    # COMPROBAR SI EXISTE EN ALGUNA RUTA
    # ==========================================

    customer_id_str = str(object_id)


    route_using_customer = await routes_collection.find_one(
        {
            "services.customer_id": customer_id_str
        }
    )


    if route_using_customer:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No se puede eliminar el cliente porque "
                "está asociado a una o más rutas. "
                "Desactiva el cliente en su lugar."
            ),
        )


    await customers_collection.delete_one(
        {
            "_id": object_id
        }
    )