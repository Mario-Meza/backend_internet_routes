
from pydantic import BaseModel, ConfigDict, EmailStr


# Base con los datos comunes
class TechnicianBase(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    active: bool = True
    specialties: list[str] = ["General"]
    photo_url: str | None = None


# Esquema para registrar un técnico nuevo (recibe password en texto plano)
class TechnicianCreate(TechnicianBase):
    password: str

# Esquema para actualizar datos generales
class TechnicianUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    specialties: list[str] = ["General"]

# Esquema para activar/desactivar
class TechnicianActiveUpdate(BaseModel):
    active: bool

# Esquema interno para interactuar con la base de datos (tiene el hash)
class TechnicianDB(TechnicianBase):
    id: str | None = None
    hashed_password: str

# Esquema que se devuelve al frontend (¡nunca incluye contraseñas!)
class TechnicianResponse(TechnicianBase):
    id: str
    model_config = ConfigDict(from_attributes=True)

