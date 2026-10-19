# core/security.py
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from core.database import technicians_collection
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
import bcrypt
from dotenv import load_dotenv

# Esto le dice a FastAPI dónde está el endpoint de login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

load_dotenv()

# Usar nombres descriptivos para JWT
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256") # Valor por defecto si no está en el .env
# Convertir el valor recuperado del .env (str) a entero (int)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def get_password_hash(password: str) -> str:
    # Genera la sal, crea el hash y lo convierte a texto normal (decode) para guardarlo en la BD
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_bytes.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# NUEVA FUNCIÓN: Obtener el técnico actual a partir del token
async def get_current_technician(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Desencriptamos el token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        technician_id: str = payload.get("id")

        if technician_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Buscamos al técnico en MongoDB
    technician = await technicians_collection.find_one({"_id": ObjectId(technician_id)})

    if technician is None or not technician.get("active", True):
        raise credentials_exception

    return technician