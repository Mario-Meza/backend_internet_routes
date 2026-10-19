from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from core.config import ADMIN_EMAIL, ADMIN_PASSWORD
# Ajusta estas importaciones a las rutas de tu proyecto:
from core.config import settings
from core.security import verify_password, get_password_hash
from core.database import database

router = APIRouter(prefix="/admin", tags=["Admin"])


# --- ESQUEMA PYDANTIC ---
class AdminUpdate(BaseModel):
    name: str
    email: EmailStr
    current_password: str
    new_password: Optional[str] = None


# --- ENDPOINT: OBTENER PERFIL ---
@router.get("/profile")
async def get_profile():
    admin = await database.admins.find_one({})

    # Migración automática: Si no existe en BD, lo crea desde el .env
    if not admin:
        new_admin = {
            "name": "Administrador Maestro",
            "email": ADMIN_EMAIL,
            "password": get_password_hash(ADMIN_PASSWORD),
            "role": "admin"
        }
        await database.admins.insert_one(new_admin)
        return {"name": new_admin["name"], "email": new_admin["email"]}

    return {
        "name": admin.get("name", "Administrador Maestro"),
        "email": admin["email"]
    }


# --- ENDPOINT: ACTUALIZAR PERFIL ---
@router.put("/profile")
async def update_profile(data: AdminUpdate):
    admin = await database.admins.find_one({})
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado en la base de datos.")

    # 1. Validar la contraseña actual
    if not verify_password(data.current_password, admin["password"]):
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta.")

    # 2. Preparar datos a actualizar
    update_data = {
        "name": data.name,
        "email": data.email
    }

    # 3. Si el usuario envió una contraseña nueva, la hasheamos
    if data.new_password:
        update_data["password"] = get_password_hash(data.new_password)

    # 4. Actualizar en MongoDB
    await database.admins.update_one(
        {"_id": admin["_id"]},
        {"$set": update_data}
    )

    return {"message": "Perfil actualizado correctamente."}