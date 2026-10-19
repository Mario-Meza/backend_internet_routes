from pydantic import BaseModel, EmailStr
from typing import Optional

# Base con los datos comunes
class TechnicianBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    active: bool = True
    photo_url: Optional[str] = None

# Esquema para registrar un técnico nuevo (recibe password en texto plano)
class TechnicianCreate(TechnicianBase):
    password: str

# Esquema para actualizar datos generales
class TechnicianUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

# Esquema para activar/desactivar
class TechnicianActiveUpdate(BaseModel):
    active: bool

# Esquema interno para interactuar con la base de datos (tiene el hash)
class TechnicianDB(TechnicianBase):
    id: Optional[str] = None
    hashed_password: str

# Esquema que se devuelve al frontend (¡nunca incluye contraseñas!)
class TechnicianResponse(TechnicianBase):
    id: str

    class Config:
        from_attributes = True