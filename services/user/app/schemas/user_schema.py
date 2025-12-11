from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_serializer, model_validator


class Permissions(BaseModel):
    can_book: bool = False
    can_manage_resources: bool = False
    can_manage_users: bool = False
    can_view_all_bookings: bool = False


def _ensure_profile_metadata(data):
    if isinstance(data, dict) and "metadata" in data and "profile_metadata" not in data:
        data = dict(data)
        data["profile_metadata"] = data.pop("metadata")
    return data


class UserBase(BaseModel):
    tenant_id: UUID = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    name: str = Field(..., examples=["João Silva"])
    email: EmailStr = Field(..., examples=["joao.silva@exemplo.com"])
    phone: Optional[str] = Field(default=None, examples=["11987654321"])
    user_type: str = Field(..., pattern="^(admin|user)$", examples=["user"])
    department: Optional[str] = Field(default=None, examples=["Recursos Humanos"])
    is_active: bool = Field(default=True, examples=[True])
    permissions: Permissions = Field(default_factory=Permissions)
    profile_metadata: Dict[str, Any] = Field(default_factory=dict, examples=[{"preferencia": "valor"}])

    @model_validator(mode="before")
    @classmethod
    def _consume_metadata_alias(cls, data):
        return _ensure_profile_metadata(data)

    @model_serializer(mode="wrap")
    def _serialize_metadata(self, handler):
        payload = handler(self)
        payload["metadata"] = payload.pop("profile_metadata", {})
        return payload

    model_config = ConfigDict(populate_by_name=True)


class UserCreate(UserBase):
    password: Optional[str] = Field(default=None, min_length=8, examples=["senha123"])


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    user_type: Optional[str] = Field(default=None, pattern="^(admin|user)$")
    department: Optional[str] = None
    is_active: Optional[bool] = None
    permissions: Optional[Permissions] = None
    profile_metadata: Optional[Dict[str, Any]] = None
    password: Optional[str] = Field(default=None, min_length=8)

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _consume_metadata_alias(cls, data):
        return _ensure_profile_metadata(data)


class UserOut(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
