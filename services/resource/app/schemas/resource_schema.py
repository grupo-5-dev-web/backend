from datetime import date, datetime
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class CategoryCustomField(BaseModel):
    key: str
    type: str = Field(..., description="Tipo do campo customizado, ex: string, number")
    required: bool = False


class ResourceCategoryBase(BaseModel):
    tenant_id: UUID = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    name: str = Field(..., examples=["Sala de Reunião"])
    description: Optional[str] = Field(default=None, examples=["Salas para reuniões e apresentações"])
    type: str = Field(..., pattern="^(fisico|humano)$", examples=["fisico"])
    icon: Optional[str] = Field(default=None, examples=["meeting_room"])
    color: Optional[str] = Field(default=None, examples=["#3B82F6"])
    is_active: bool = Field(default=True, examples=[True])
    category_metadata: Dict[str, Any] = Field(default_factory=dict, examples=[{"requires_qualification": False}])


class ResourceCategoryCreate(ResourceCategoryBase):
    category_metadata: Dict[str, Any] = Field(default_factory=lambda: {
        "requires_qualification": False,
        "allows_multiple_bookings": False,
        "custom_fields": []
    })


class ResourceCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = Field(default=None, pattern="^(fisico|humano)")
    icon: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None
    category_metadata: Optional[Dict[str, Any]] = None


class ResourceCategoryOut(ResourceCategoryBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceBase(BaseModel):
    tenant_id: UUID = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    category_id: UUID = Field(..., examples=["660e8400-e29b-41d4-a716-446655440001"])
    name: str = Field(..., examples=["Sala 101"])
    description: Optional[str] = Field(default=None, examples=["Sala com capacidade para 10 pessoas"])
    status: str = Field(default="disponivel", pattern="^(disponivel|manutencao|indisponivel)$", examples=["disponivel"])
    capacity: Optional[int] = Field(default=None, ge=1, examples=[10])
    location: Optional[str] = Field(default=None, examples=["1º andar, ala oeste"])
    attributes: Dict[str, Any] = Field(default_factory=dict, examples=[{"projetor": True, "ar_condicionado": True}])
    availability_schedule: Dict[str, Any] = Field(default_factory=dict, examples=[{"monday": ["09:00-18:00"], "friday": ["09:00-17:00"]}])
    image_url: Optional[HttpUrl] = Field(default=None, examples=["https://exemplo.com/sala101.jpg"])


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(disponivel|manutencao|indisponivel)$")
    capacity: Optional[int] = Field(default=None, ge=1)
    location: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    availability_schedule: Optional[Dict[str, Any]] = None
    image_url: Optional[HttpUrl] = None


class ResourceOut(ResourceBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    category: Optional[ResourceCategoryOut] = None

    model_config = ConfigDict(from_attributes=True)


class AvailabilitySlotOut(BaseModel):
    start_time: datetime
    end_time: datetime


class ResourceAvailabilityResponse(BaseModel):
    resource_id: UUID
    tenant_id: UUID
    date: date
    timezone: str
    slots: list[AvailabilitySlotOut]
