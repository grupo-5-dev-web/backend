from datetime import time, datetime
from uuid import UUID
from typing import Literal
from typing import Optional, Self
from pydantic import BaseModel, HttpUrl, ConfigDict, Field, field_validator, model_validator


class CustomLabels(BaseModel):
    resource_singular: str = Field(..., examples=["Recurso"])
    resource_plural: str = Field(..., examples=["Recursos"])
    booking_label: str = Field(..., examples=["Agendamento"])
    user_label: str = Field(..., examples=["Usuário"])


class OrganizationSettingsBase(BaseModel):
    business_type: str = Field(..., examples=["Clínica Médica"])
    timezone: str = Field(default="UTC", examples=["America/Sao_Paulo"])
    working_hours_start: time = Field(..., examples=["08:00:00"])
    working_hours_end: time = Field(..., examples=["18:00:00"])
    booking_interval: int = Field(ge=5, le=480, default=30, examples=[30])
    advance_booking_days: int = Field(ge=0, le=365, default=30, examples=[30])
    cancellation_hours: int = Field(ge=0, le=168, default=24, examples=[24])
    custom_labels: CustomLabels

    @model_validator(mode="after")
    def validar_horarios(self) -> Self:
        if self.working_hours_start >= self.working_hours_end:
            raise ValueError("working_hours_start deve ser menor que working_hours_end")
        return self


class OrganizationSettingsCreate(OrganizationSettingsBase):
    pass


class OrganizationSettingsUpdate(BaseModel):
    timezone: Optional[str] = None
    working_hours_start: Optional[time] = None
    working_hours_end: Optional[time] = None
    booking_interval: Optional[int] = Field(default=None, ge=5, le=480)
    advance_booking_days: Optional[int] = Field(default=None, ge=0, le=365)
    cancellation_hours: Optional[int] = Field(default=None, ge=0, le=168)
    custom_labels: Optional[CustomLabels] = None

    @model_validator(mode="after")
    def validar_horarios(self) -> Self:
        if (
            self.working_hours_start
            and self.working_hours_end
            and self.working_hours_start >= self.working_hours_end
        ):
            raise ValueError("working_hours_start deve ser menor que working_hours_end")
        return self


class OrganizationSettingsOut(OrganizationSettingsBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenantBase(BaseModel):
    name: str = Field(..., examples=["Clínica Saúde Total"])
    domain: str = Field(..., examples=["clinica-saude-total"])
    logo_url: HttpUrl = Field(..., examples=["https://exemplo.com/logo.png"])
    theme_primary_color: str = Field(..., examples=["#4A90E2"])
    plan: Literal["basico", "profissional", "corporativo"] = Field(..., examples=["profissional"])
    is_active: bool = Field(default=True, examples=[True])

    @field_validator("theme_primary_color")
    @classmethod
    def validar_hex_color(cls, value: str) -> str:
        if not value.startswith("#") or len(value) not in {4, 7}:
            raise ValueError("Cor deve estar no formato hexadecimal, ex: #RRGGBB")
        return value


class TenantCreate(TenantBase):
    settings: OrganizationSettingsCreate


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    logo_url: Optional[HttpUrl] = None
    theme_primary_color: Optional[str] = None
    plan: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("theme_primary_color")
    @classmethod
    def validar_hex_color_update(cls, value: Optional[str]) -> Optional[str]:
        if value and (not value.startswith("#") or len(value) not in {4, 7}):
            raise ValueError("Cor deve estar no formato hexadecimal, ex: #RRGGBB")
        return value


class TenantOut(TenantBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    settings: OrganizationSettingsOut

    model_config = ConfigDict(from_attributes=True)