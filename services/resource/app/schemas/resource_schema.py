from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class CategoryCustomField(BaseModel):
    key: str
    type: str = Field(..., description="Tipo do campo customizado, ex: string, number")
    required: bool = False


class ResourceCategoryBase(BaseModel):
    tenant_id: UUID
    name: str
    description: Optional[str] = None
    type: str = Field(..., pattern="^(physical|human|software)$")
    icon: Optional[str] = None
    color: Optional[str] = None
    is_active: bool = True
    category_metadata: Dict[str, Any] = Field(default_factory=dict)


class ResourceCategoryCreate(ResourceCategoryBase):
    category_metadata: Dict[str, Any] = Field(default_factory=lambda: {
        "requires_qualification": False,
        "allows_multiple_bookings": False,
        "custom_fields": []
    })


class ResourceCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = Field(default=None, pattern="^(physical|human|software)$")
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
    tenant_id: UUID
    category_id: UUID
    name: str
    description: Optional[str] = None
    status: str = Field(default="disponivel", pattern="^(disponivel|manutencao|indisponivel)$")
    capacity: Optional[int] = Field(default=None, ge=1)
    location: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    availability_schedule: Dict[str, Any] = Field(default_factory=dict)
    image_url: Optional[HttpUrl] = None


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
