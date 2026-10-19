from bson import ObjectId
from fastapi import APIRouter, HTTPException, status
import os
import cloudinary.uploader
from fastapi import (
    APIRouter,
    HTTPException,
    status,
    UploadFile,
    File,
)
from starlette.concurrency import run_in_threadpool
from core.cloudinary_config import cloudinary


from core.database import (
    routes_collection,
    technicians_collection,
)

from schemas.technician import (
    TechnicianActiveUpdate,
    TechnicianCreate,
    TechnicianResponse,
    TechnicianUpdate,
)
from core.security import get_password_hash

router = APIRouter(
    prefix="/technicians",
    tags=["Technicians"],
)


def validate_object_id(
    technician_id: str,
) -> ObjectId:

    if not ObjectId.is_valid(technician_id):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de técnico inválido",
        )

    return ObjectId(technician_id)


def technician_to_response(technician: dict) -> TechnicianResponse:
    return TechnicianResponse(
        id=str(technician["_id"]),
        name=technician["name"],
        email=technician.get("email", "sin-correo@pendiente.com"), # Agregamos el correo aquí
        phone=technician.get("phone"),
        active=technician.get("active", True),
        photo_url=technician.get("photo_url"),
    )


# ==========================================
# CREAR TÉCNICO
# ==========================================

# ==========================================
# CREAR TÉCNICO
# ==========================================

@router.post(
    "/",
    response_model=TechnicianResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_technician(technician: TechnicianCreate):
    # 1. (Opcional) Validar si el correo ya existe
    # existing_user = await technicians_collection.find_one({"email": technician.email})
    # if existing_user:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="El correo ya está registrado"
    #     )

    # 2. Generar el hash de la contraseña
    hashed_pw = get_password_hash(technician.password)

    # 3. Preparar los datos para la BD: excluir 'password' en texto plano
    #    y agregar 'hashed_password' y 'active' por defecto.
    technician_data = technician.model_dump(exclude={"password"})
    technician_data["hashed_password"] = hashed_pw
    technician_data["active"] = True

    # 4. Insertar en MongoDB
    result = await technicians_collection.insert_one(technician_data)

    # 5. Obtener el técnico recién creado usando su nuevo _id
    created_technician = await technicians_collection.find_one(
        {"_id": result.inserted_id}
    )

    # 6. Retornar con el formato seguro (sin exponer la contraseña)
    return technician_to_response(created_technician)



    technician_data = technician.model_dump()

    technician_data["active"] = True


    result = await technicians_collection.insert_one(
        technician_data
    )


    created_technician = (
        await technicians_collection.find_one(
            {
                "_id": result.inserted_id
            }
        )
    )


    return technician_to_response(
        created_technician
    )


# ==========================================
# LISTAR TÉCNICOS
# ==========================================

@router.get(
    "/",
    response_model=list[TechnicianResponse],
)
async def get_technicians():

    technicians = []


    cursor = technicians_collection.find().sort(
        "name",
        1,
    )


    async for technician in cursor:

        technicians.append(
            technician_to_response(
                technician
            )
        )


    return technicians


# ==========================================
# OBTENER TÉCNICO
# ==========================================

@router.get(
    "/{technician_id}",
    response_model=TechnicianResponse,
)
async def get_technician(
    technician_id: str,
):

    object_id = validate_object_id(
        technician_id
    )


    technician = await technicians_collection.find_one(
        {
            "_id": object_id
        }
    )


    if not technician:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Técnico no encontrado",
        )


    return technician_to_response(
        technician
    )


# ==========================================
# ACTUALIZAR TÉCNICO
# ==========================================

@router.put(
    "/{technician_id}",
    response_model=TechnicianResponse,
)
async def update_technician(
    technician_id: str,
    technician: TechnicianUpdate,
):

    object_id = validate_object_id(
        technician_id
    )


    existing_technician = (
        await technicians_collection.find_one(
            {
                "_id": object_id
            }
        )
    )


    if not existing_technician:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Técnico no encontrado",
        )


    update_data = technician.model_dump(
        exclude_unset=True
    )


    if not update_data:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay datos para actualizar",
        )


    await technicians_collection.update_one(
        {
            "_id": object_id
        },
        {
            "$set": update_data
        },
    )


    updated_technician = (
        await technicians_collection.find_one(
            {
                "_id": object_id
            }
        )
    )


    return technician_to_response(
        updated_technician
    )


# ==========================================
# ACTIVAR / DESACTIVAR
# ==========================================

@router.patch(
    "/{technician_id}/active",
    response_model=TechnicianResponse,
)
async def update_technician_active(
    technician_id: str,
    data: TechnicianActiveUpdate,
):

    object_id = validate_object_id(
        technician_id
    )


    result = await technicians_collection.update_one(
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
            detail="Técnico no encontrado",
        )


    technician = (
        await technicians_collection.find_one(
            {
                "_id": object_id
            }
        )
    )


    return technician_to_response(
        technician
    )


# ==========================================
# SUBIR FOTOGRAFÍA DEL TÉCNICO
# ==========================================

@router.post(
    "/{technician_id}/photo",
    response_model=TechnicianResponse,
)
async def upload_technician_photo(
    technician_id: str,
    file: UploadFile = File(...),
):
    object_id = validate_object_id(technician_id)

    technician = await technicians_collection.find_one(
        {"_id": object_id}
    )

    if not technician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Técnico no encontrado",
        )

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="La fotografía debe ser JPG, PNG o WEBP",
        )

    image_bytes = await file.read(5 * 1024 * 1024 + 1)

    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío",
        )

    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="La fotografía no debe superar los 5 MB",
        )

    # Subir la nueva imagen a Cloudinary.
    try:
        upload_result = await run_in_threadpool(
            cloudinary.uploader.upload,
            image_bytes,
            folder="rutas_digitales/technicians",
            resource_type="image",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo subir la fotografía",
        ) from exc

    photo_url = upload_result["secure_url"]
    photo_public_id = upload_result["public_id"]

    # Guardar la URL y el identificador de Cloudinary.
    await technicians_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "photo_url": photo_url,
                "photo_public_id": photo_public_id,
            }
        },
    )

    # Eliminar la imagen anterior después de guardar la nueva.
    old_public_id = technician.get("photo_public_id")

    if old_public_id:
        try:
            await run_in_threadpool(
                cloudinary.uploader.destroy,
                old_public_id,
                resource_type="image",
            )
        except Exception:
            # La nueva fotografía ya quedó guardada.
            # La anterior podrá eliminarse después.
            pass

    updated_technician = await technicians_collection.find_one(
        {"_id": object_id}
    )

    return technician_to_response(updated_technician)


# ==========================================
# ELIMINAR FOTOGRAFÍA DEL TÉCNICO
# ==========================================

@router.delete(
    "/{technician_id}/photo",
    response_model=TechnicianResponse,
)
async def delete_technician_photo(
    technician_id: str,
):
    object_id = validate_object_id(technician_id)

    technician = await technicians_collection.find_one(
        {"_id": object_id}
    )

    if not technician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Técnico no encontrado",
        )

    public_id = technician.get("photo_public_id")

    if public_id:
        try:
            result = await run_in_threadpool(
                cloudinary.uploader.destroy,
                public_id,
                resource_type="image",
            )

            if result.get("result") not in {"ok", "not found"}:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="No se pudo eliminar la fotografía",
                )

        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Error al eliminar la fotografía",
            ) from exc

    await technicians_collection.update_one(
        {"_id": object_id},
        {
            "$unset": {
                "photo_url": "",
                "photo_public_id": "",
            }
        },
    )

    updated_technician = await technicians_collection.find_one(
        {"_id": object_id}
    )

    return technician_to_response(updated_technician)


# ==========================================
# ELIMINAR TÉCNICO
# ==========================================

@router.delete(
    "/{technician_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_technician(
    technician_id: str,
):

    object_id = validate_object_id(
        technician_id
    )


    technician = (
        await technicians_collection.find_one(
            {
                "_id": object_id
            }
        )
    )


    if not technician:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Técnico no encontrado",
        )


    technician_id_str = str(object_id)


    # ==========================================
    # COMPROBAR SI TIENE RUTAS
    # ==========================================

    route_using_technician = (
        await routes_collection.find_one(
            {
                "technician_id": technician_id_str
            }
        )
    )


    if route_using_technician:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No se puede eliminar el técnico porque "
                "está asociado a una o más rutas. "
                "Desactiva el técnico en su lugar."
            ),
        )


    await technicians_collection.delete_one(
        {
            "_id": object_id
        }
    )