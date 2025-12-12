"""Modelo de Webhook para notificações de eventos."""

import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Webhook(Base):
    """Modelo para webhooks configuráveis por tenant."""
    
    __tablename__ = "webhooks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(String, nullable=False)
    events = Column(ARRAY(String), nullable=False)  # Lista de eventos: ["booking.created", "booking.cancelled"]
    secret = Column(String, nullable=True)  # Secret opcional para assinatura HMAC
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    tenant = relationship("Tenant", back_populates="webhooks")

