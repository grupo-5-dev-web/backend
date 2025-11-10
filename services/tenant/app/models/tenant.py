# app/models/tenant.py
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Time, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    domain = Column(String, unique=True, nullable=False, index=True)
    logo_url = Column(String, nullable=False)
    theme_primary_color = Column(String, nullable=False)
    plan = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    settings = relationship("OrganizationSettings", back_populates="tenant", cascade="all, delete-orphan", uselist=False)


class OrganizationSettings(Base):
    __tablename__ = "organization_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False)
    business_type = Column(String, nullable=False)
    timezone = Column(String, nullable=False, default="UTC")
    working_hours_start = Column(Time, nullable=False)
    working_hours_end = Column(Time, nullable=False)
    booking_interval = Column(Integer, nullable=False, default=30)
    advance_booking_days = Column(Integer, nullable=False, default=30)
    cancellation_hours = Column(Integer, nullable=False, default=24)
    custom_labels = Column(JSONB().with_variant(JSON, "sqlite"), nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="settings")
