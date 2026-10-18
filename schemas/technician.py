
from pydantic import BaseModel, Field
from typing import Optional


class TechnicianCreate(BaseModel):
    name: str
    phone: str


class TechnicianUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


class TechnicianActiveUpdate(BaseModel):
    active: bool


class TechnicianResponse(BaseModel):
    id: str
    name: str
    phone: str
    active: bool = True
    photo_url: Optional[str] = None