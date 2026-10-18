from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


# ==========================================
# TIPOS DE SERVICIO
# ==========================================

class ServiceType(str, Enum):
    SERVICE = "S"
    RECONNECTION = "R"
    ALIGN = "A"
    CHANGE_TO_FIBER = "CF"

# ==========================================
# ESTADOS DEL SERVICIO
# ==========================================

class ServiceStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NOT_COMPLETED = "no_completed"
    CANCELED = "cancelled"

# ==========================================
# ESTADOS DE LA RUTA
# ==========================================

class RouteStatus(str, Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELED = "canceled"


# ==========================================
# SERVICIO AL CREAR
# ==========================================

class RouteServiceCreate(BaseModel):
    customer_id: str
    service_type: ServiceType


# ==========================================
# SERVICIO AL ACTUALIZAR
# ==========================================

class RouteServiceUpdate(BaseModel):
    customer_id: str | None = None
    service_type: ServiceType | None = None


# ==========================================
# SERVICIO EN RESPUESTA
# ==========================================

class RouteServiceResponse(BaseModel):
    service_id: str
    customer_id: str
    service_type: ServiceType
    status: ServiceStatus

    notes: str | None = None

    started_at: datetime | None = None
    completed_at: datetime | None = None


# ==========================================
# COMPLETAR SERVICIO
# ==========================================

class CompleteServiceRequest(BaseModel):
    notes: str | None = Field(
        default=None,
        max_length=500,
    )


# ==========================================
# CREAR RUTA
# ==========================================

class RouteCreate(BaseModel):
    route_date: date
    technician_id: str

    services: list[RouteServiceCreate] = Field(
        min_length=1,
    )


# ==========================================
# ACTUALIZAR RUTA
# ==========================================

class RouteUpdate(BaseModel):
    route_date: date | None = None
    technician_id: str | None = None


# ==========================================
# ACTUALIZAR ESTADO DE RUTA
# ==========================================

class RouteStatusUpdate(BaseModel):
    status: RouteStatus


# ==========================================
# CLIENTE RESUMIDO
# ==========================================

class CustomerSummary(BaseModel):
    id: str
    name: str
    phone: str
    location: str
    reference: str | None = None


# ==========================================
# TÉCNICO RESUMIDO
# ==========================================

class TechnicianSummary(BaseModel):
    id: str
    name: str
    phone: str | None = None
    active: bool


# ==========================================
# SERVICIO DETALLE
# ==========================================

class RouteServiceDetailResponse(
    RouteServiceResponse
):
    customer: CustomerSummary | None = None


# ==========================================
# RESPUESTA NORMAL DE RUTA
# ==========================================

class RouteResponse(BaseModel):
    id: str
    route_date: date
    technician_id: str
    status: RouteStatus
    services: list[RouteServiceResponse]


# ==========================================
# RESPUESTA DETALLE
# ==========================================

class RouteDetailResponse(BaseModel):
    id: str
    route_date: date
    technician_id: str
    technician: TechnicianSummary
    status: RouteStatus
    services: list[RouteServiceDetailResponse]