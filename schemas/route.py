# schemas/route.py
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RouteStatus(StrEnum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELED = "canceled"


class ServiceStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NOT_COMPLETED = "not_completed"
    CANCELED = "canceled"


class ServiceType(StrEnum):
    SERVICE = "S"
    RECONNECTION = "R"
    ALIGN = "A"
    CHANGE_TO_FIBER = "CF"


class RouteCustomerSummary(BaseModel):
    id: str
    name: str
    phone: str | None = None
    location: str | None = None
    reference: str | None = None


class RouteTechnicianSummary(BaseModel):
    id: str
    name: str
    phone: str | None = None
    active: bool = True


class RouteServiceCreate(BaseModel):
    customer_id: str
    service_type: ServiceType


class RouteServiceUpdate(BaseModel):
    customer_id: str | None = None
    service_type: ServiceType | None = None


class CompleteServiceRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)


class RouteServiceResponse(BaseModel):
    service_id: str
    customer_id: str
    service_type: str
    status: ServiceStatus
    notes: str | None = None
    evidence_url: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RouteServiceDetailResponse(RouteServiceResponse):
    customer: RouteCustomerSummary | None = None


class RouteCreate(BaseModel):
    route_date: date
    technician_id: str
    services: list[RouteServiceCreate] = Field(default_factory=list)
    notes: str | None = None


class RouteUpdate(BaseModel):
    route_date: date | None = None
    technician_id: str | None = None
    notes: str | None = None


class RouteStatusUpdate(BaseModel):
    status: RouteStatus


class RouteResponse(BaseModel):
    id: str
    route_date: date
    technician_id: str
    status: RouteStatus
    notes: str | None = None
    services: list[RouteServiceResponse] = Field(default_factory=list)


class RouteDetailResponse(BaseModel):
    id: str
    route_date: date
    technician_id: str
    technician: RouteTechnicianSummary
    status: RouteStatus
    notes: str | None = None
    services: list[RouteServiceDetailResponse] = Field(default_factory=list)