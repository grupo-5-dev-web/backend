from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.booking import BookingStatus


class RecurringPattern(BaseModel):
    frequency: str = Field(pattern="^(daily|weekly|monthly)$")
    interval: int = Field(ge=1, le=52, default=1)
    end_date: Optional[datetime] = None
    days_of_week: Optional[list[int]] = Field(default=None)

    @field_validator("days_of_week")
    @classmethod
    def validar_dias_semana(cls, value, info):
        if value is None:
            return value
        if not all(0 <= day <= 6 for day in value):
            raise ValueError("days_of_week deve conter valores de 0 a 6")
        return value


class BookingBase(BaseModel):
    tenant_id: UUID
    resource_id: UUID
    user_id: UUID
    client_id: Optional[UUID] = None
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None
    recurring_enabled: bool = False
    recurring_pattern: Optional[RecurringPattern] = None

    @field_validator("end_time")
    @classmethod
    def validar_intervalo(cls, end_time, info):
        start_time = info.data.get("start_time")
        if start_time and end_time <= start_time:
            raise ValueError("end_time deve ser maior que start_time")
        return end_time


class BookingCreate(BookingBase):
    status: Optional[str] = Field(default=BookingStatus.PENDING)

    @field_validator("status")
    @classmethod
    def validar_status(cls, value):
        if value not in BookingStatus.ALL:
            raise ValueError("Status inválido")
        return value


class BookingUpdate(BaseModel):
    resource_id: Optional[UUID] = None
    client_id: Optional[UUID] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    notes: Optional[str] = None
    status: Optional[str] = Field(default=None)
    recurring_enabled: Optional[bool] = None
    recurring_pattern: Optional[RecurringPattern] = None

    @field_validator("status")
    @classmethod
    def validar_status(cls, value):
        if value and value not in BookingStatus.ALL:
            raise ValueError("Status inválido")
        return value

    @field_validator("end_time")
    @classmethod
    def validar_intervalo(cls, end_time, info):
        start_time = info.data.get("start_time")
        if start_time and end_time and end_time <= start_time:
            raise ValueError("end_time deve ser maior que start_time")
        return end_time


class BookingOut(BaseModel):
    id: UUID
    tenant_id: UUID
    resource_id: UUID
    user_id: UUID
    client_id: Optional[UUID]
    start_time: datetime
    end_time: datetime
    status: str
    notes: Optional[str]
    confirmation_code: Optional[str]
    recurring_enabled: bool
    recurring_pattern: Optional[Dict[str, Any]]
    cancellation_reason: Optional[str]
    cancelled_at: Optional[datetime]
    cancelled_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingCancelRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class BookingConflict(BaseModel):
    booking_id: UUID
    start_time: datetime
    end_time: datetime


class BookingConflictResponse(BaseModel):
    success: bool
    error: str
    message: str
    conflicts: list[BookingConflict]


class BookingWithPolicy(BookingOut):
    can_cancel: bool