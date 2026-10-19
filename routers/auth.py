from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from core.security import verify_password, create_access_token
# Importamos la nueva colección de administradores
from core.database import technicians_collection, admin_collection
from core.config import ADMIN_EMAIL, ADMIN_PASSWORD

router = APIRouter(tags=["Authentication"])


@router.post("/login")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # 1. VERIFICAR SI ES EL ADMINISTRADOR
    # Primero buscamos en la base de datos
    admin_db = await admin_collection.find_one({"email": form_data.username})

    is_admin_valid = False

    if admin_db:
        # Si el administrador ya se migró a la base de datos, verificamos la contraseña encriptada
        if verify_password(form_data.password, admin_db["password"]):
            is_admin_valid = True
    else:
        # SALVAVIDAS (FALLBACK): Si no existe en la BD (es decir, aún no visita /profile),
        # usamos las variables del entorno (.env) para dejarlo entrar por primera vez.
        if form_data.username == ADMIN_EMAIL and form_data.password == ADMIN_PASSWORD:
            is_admin_valid = True

    # Si la validación de admin fue exitosa (ya sea por BD o por .env)
    if is_admin_valid:
        access_token = create_access_token(
            data={
                "sub": form_data.username,
                "role": "admin"
            }
        )
        return {"access_token": access_token, "token_type": "bearer", "role": "admin"}

    # 2. SI NO ES ADMIN, BUSCAR EN TÉCNICOS
    technician = await technicians_collection.find_one({"email": form_data.username})

    if not technician or not technician.get("active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Verificar que la contraseña coincida con el hash
    if not verify_password(form_data.password, technician["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Generar y retornar el Token JWT
    access_token = create_access_token(
        data={
            "sub": technician["email"],
            "id": str(technician["_id"]),
            "role": "technician"
        }
    )

    return {"access_token": access_token, "token_type": "bearer", "role": "technician"}