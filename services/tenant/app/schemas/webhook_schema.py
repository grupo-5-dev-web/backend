"""Schemas para webhooks."""

from datetime import datetime
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict
from shared import validate_webhook_url


class WebhookBase(BaseModel):
    """Schema base para webhook."""
    url: str = Field(..., examples=["https://example.com/webhook"])
    events: List[str] = Field(..., examples=[["booking.created", "booking.cancelled"]])
    secret: Optional[str] = Field(None, examples=["my-secret-key"])
    is_active: bool = Field(default=True, examples=[True])
    
    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """Valida se a URL é segura."""
        if not validate_webhook_url(value):
            raise ValueError(
                "URL inválida. Use HTTPS ou HTTP apenas para localhost/127.0.0.1"
            )
        return value
    
    @field_validator("events")
    @classmethod
    def validate_events(cls, value: List[str]) -> List[str]:
        """Valida se os eventos são suportados."""
        valid_events = {"booking.created", "booking.cancelled", "booking.updated", "booking.status_changed"}
        invalid_events = set(value) - valid_events
        if invalid_events:
            raise ValueError(
                f"Eventos inválidos: {invalid_events}. "
                f"Eventos suportados: {valid_events}"
            )
        if not value:
            raise ValueError("Pelo menos um evento deve ser especificado")
        return value


class WebhookCreate(WebhookBase):
    """Schema para criação de webhook."""
    pass


class WebhookUpdate(BaseModel):
    """Schema para atualização de webhook."""
    url: Optional[str] = None
    events: Optional[List[str]] = None
    secret: Optional[str] = None
    is_active: Optional[bool] = None
    
    @field_validator("url")
    @classmethod
    def validate_url(cls, value: Optional[str]) -> Optional[str]:
        """Valida se a URL é segura."""
        if value is not None and not validate_webhook_url(value):
            raise ValueError(
                "URL inválida. Use HTTPS ou HTTP apenas para localhost/127.0.0.1"
            )
        return value
    
    @field_validator("events")
    @classmethod
    def validate_events(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        """Valida se os eventos são suportados."""
        if value is None:
            return value
        valid_events = {"booking.created", "booking.cancelled", "booking.updated", "booking.status_changed"}
        invalid_events = set(value) - valid_events
        if invalid_events:
            raise ValueError(
                f"Eventos inválidos: {invalid_events}. "
                f"Eventos suportados: {valid_events}"
            )
        if not value:
            raise ValueError("Pelo menos um evento deve ser especificado")
        return value


class WebhookOut(WebhookBase):
    """Schema para resposta de webhook."""
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

