import uuid
from sqlalchemy import Boolean, Column, DateTime, String, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.core.database import Base


def default_permissions():
    return {
        "can_book": False,
        "can_manage_resources": False,
        "can_manage_users": False,
        "can_view_all_bookings": False,
    }


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    user_type = Column(String, nullable=False)
    department = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    permissions = Column(JSONB().with_variant(JSON, "sqlite"), nullable=False, default=default_permissions)
    profile_metadata = Column(JSONB().with_variant(JSON, "sqlite"), nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
