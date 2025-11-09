import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.core.database import Base


class BookingStatus:
    PENDING = "pendente"
    CONFIRMED = "confirmado"
    CANCELLED = "cancelado"
    COMPLETED = "concluido"
    NO_SHOW = "nao_compareceu"

    ALL = {PENDING, CONFIRMED, CANCELLED, COMPLETED, NO_SHOW}


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        Index("ix_bookings_resource_interval", "tenant_id", "resource_id", "start_time", "end_time"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    resource_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    client_id = Column(UUID(as_uuid=True), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False, default=BookingStatus.PENDING)
    notes = Column(Text, nullable=True)
    confirmation_code = Column(String, nullable=True, unique=True)

    recurring_enabled = Column(Boolean, default=False)
    recurring_pattern = Column(JSONB, nullable=True)

    cancellation_reason = Column(Text, nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_by = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BookingEvent(Base):
    __tablename__ = "booking_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())