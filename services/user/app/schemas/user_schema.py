from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Permissions(BaseModel):
    can_book: bool = False
    can_manage_resources: bool = False
    can_manage_users: bool = False
    can_view_all_bookings: bool = False


class UserBase(BaseModel):
    tenant_id: UUID
    name: str
    email: EmailStr
    phone: Optional[str] = None
    user_type: str = Field(pattern="^(admin|manager|professional|client)$")
    department: Optional[str] = None
    is_active: bool = True
    permissions: Permissions = Permissions()
    profile_metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class UserCreate(UserBase):
    password: Optional[str] = Field(default=None, min_length=8)


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    user_type: Optional[str] = Field(default=None, pattern="^(admin|manager|professional|client)$")
    department: Optional[str] = None
    is_active: Optional[bool] = None
    permissions: Optional[Permissions] = None
    profile_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata")
    password: Optional[str] = Field(default=None, min_length=8)

    model_config = ConfigDict(populate_by_name=True)


class UserOut(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
