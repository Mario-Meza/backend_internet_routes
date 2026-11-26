import hmac
import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from core.config import ADMIN_EMAIL, ADMIN_PASSWORD
from core.database import admin_collection, technicians_collection
from core.security import create_access_token, verify_password

router = APIRouter(tags=["Authentication"])


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Usuario o contraseña incorrectos",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _check_password(plain: str, hashed: str | None) -> bool:
    """Como verify_password, pero nunca revienta con un 500.

    Devuelve False si el documento no trae hash, si el hash es inválido o si
    la contraseña supera los 72 bytes (bcrypt 5 lanza ValueError en ese caso).
    """
    if not hashed:
        return False
    try:
        return verify_password(plain, hashed)
    except ValueError:
        return False


# OJO: el frontend envía el login como formulario (application/x-www-form-urlencoded)
# con los campos "username" y "password" (ver loginTechnician en src/services/api.ts),
# así que se mantiene OAuth2PasswordRequestForm. Un body JSON con "email" daría 422.
@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    email = form_data.username.strip().lower()
    password = form_data.password

    # 1. ADMINISTRADOR
    # admin.py asume un único admin (find_one({})), aquí se usa el mismo criterio.
    admin = await admin_collection.find_one({})

    if admin:
        # Ya existe en MongoDB: SOLO vale lo guardado en la BD (el .env deja de servir).
        # Los admins se guardan con el hash en el campo "password" (ver admin.py).
        if (admin.get("email") or "").strip().lower() == email and _check_password(
            password, admin.get("password")
        ):
            token = create_access_token(
                data={
                    "sub": admin["email"],
                    "role": "admin",
                    "id": str(admin["_id"]),
                }
            )
            return {"access_token": token, "token_type": "bearer", "role": "admin"}
    elif (
        ADMIN_EMAIL
        and ADMIN_PASSWORD
        and email == ADMIN_EMAIL.strip().lower()
        and hmac.compare_digest(password.encode(), ADMIN_PASSWORD.encode())
    ):
        # Bootstrap inicial: solo mientras no exista ningún admin en MongoDB.
        token = create_access_token(data={"sub": ADMIN_EMAIL, "role": "admin"})
        return {"access_token": token, "token_type": "bearer", "role": "admin"}

    # 2. TÉCNICO
    # Búsqueda sin distinguir mayúsculas: el correo se guarda tal como se escribió
    # al crear el técnico (p. ej. "Juan@..."), y aquí ya viene en minúsculas.
    technician = await technicians_collection.find_one(
        {"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}}
    )

    # Los técnicos guardan el hash en "hashed_password" (ver technicians.py).
    if not technician or not _check_password(
        password, technician.get("hashed_password")
    ):
        raise _invalid_credentials()

    if not technician.get("active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta está desactivada. Contacta al administrador.",
        )

    token = create_access_token(
        data={
            "sub": technician["email"],
            "id": str(technician["_id"]),
            "role": "technician",
        }
    )
    return {"access_token": token, "token_type": "bearer", "role": "technician"}