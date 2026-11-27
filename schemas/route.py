# schemas/route.py
from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RouteStatus(str, Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELED = "canceled"


class ServiceStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NOT_COMPLETED = "not_completed"
    CANCELED = "canceled"


class ServiceType(str, Enum):
    SERVICE = "S"
    RECONNECTION = "R"
    ALIGN = "A"
    CHANGE_TO_FIBER = "CF"


class RouteCustomerSummary(BaseModel):
    id: str
    name: str
    phone: Optional[str] = None
    location: Optional[str] = None
    reference: Optional[str] = None


class RouteTechnicianSummary(BaseModel):
    id: str
    name: str
    phone: Optional[str] = None
    active: bool = True


class RouteServiceCreate(BaseModel):
    customer_id: str
    service_type: ServiceType


class RouteServiceUpdate(BaseModel):
    customer_id: Optional[str] = None
    service_type: Optional[ServiceType] = None


class CompleteServiceRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=1000)


class RouteServiceResponse(BaseModel):
    service_id: str
    customer_id: str
    service_type: str
    status: ServiceStatus
    notes: Optional[str] = None
    evidence_url: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class RouteServiceDetailResponse(RouteServiceResponse):
    customer: Optional[RouteCustomerSummary] = None


class RouteCreate(BaseModel):
    route_date: date
    technician_id: str
    services: list[RouteServiceCreate] = Field(default_factory=list)
    notes: Optional[str] = None


class RouteUpdate(BaseModel):
    route_date: Optional[date] = None
    technician_id: Optional[str] = None
    notes: Optional[str] = None


class RouteStatusUpdate(BaseModel):
    status: RouteStatus


class RouteResponse(BaseModel):
    id: str
    route_date: date
    technician_id: str
    status: RouteStatus
    notes: Optional[str] = None
    services: list[RouteServiceResponse] = Field(default_factory=list)


class RouteDetailResponse(BaseModel):
    id: str
    route_date: date
    technician_id: str
    technician: RouteTechnicianSummary
    status: RouteStatus
    notes: Optional[str] = None
    services: list[RouteServiceDetailResponse] = Field(default_factory=list)