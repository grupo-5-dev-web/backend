"""initial schema

Revision ID: 20251109_3001
Revises: 
Create Date: 2025-11-09 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20251109_3001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'pendente'")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmation_code", sa.String(), nullable=True),
        sa.Column("recurring_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recurring_pattern", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("confirmation_code", name="uq_bookings_confirmation_code"),
    )
    op.create_index("ix_bookings_tenant_id", "bookings", ["tenant_id"], unique=False)
    op.create_index("ix_bookings_resource_id", "bookings", ["resource_id"], unique=False)
    op.create_index("ix_bookings_resource_interval", "bookings", ["tenant_id", "resource_id", "start_time", "end_time"], unique=False)

    op.create_table(
        "booking_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_booking_events_booking_id", "booking_events", ["booking_id"], unique=False)
    op.create_index("ix_booking_events_tenant_id", "booking_events", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_booking_events_tenant_id", table_name="booking_events")
    op.drop_index("ix_booking_events_booking_id", table_name="booking_events")
    op.drop_table("booking_events")

    op.drop_index("ix_bookings_resource_interval", table_name="bookings")
    op.drop_index("ix_bookings_resource_id", table_name="bookings")
    op.drop_index("ix_bookings_tenant_id", table_name="bookings")
    op.drop_table("bookings")
