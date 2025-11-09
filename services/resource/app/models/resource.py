import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class ResourceCategory(Base):
    __tablename__ = "resource_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    type = Column(String, nullable=False)
    icon = Column(String, nullable=True)
    color = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    category_metadata = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    resources = relationship("Resource", back_populates="category")


class Resource(Base):
    __tablename__ = "resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("resource_categories.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, nullable=False, default="disponivel")
    capacity = Column(Integer, nullable=True)
    location = Column(String, nullable=True)
    attributes = Column(JSONB, nullable=False, default=dict)
    availability_schedule = Column(JSONB, nullable=False, default=dict)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    category = relationship("ResourceCategory", back_populates="resources")
