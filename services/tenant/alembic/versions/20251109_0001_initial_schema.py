"""initial schema

Revision ID: 20251109_1001
Revises: 
Create Date: 2025-11-09 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20251109_1001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("logo_url", sa.String(), nullable=False),
        sa.Column("theme_primary_color", sa.String(), nullable=False),
        sa.Column("plan", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain", name="uq_tenants_domain"),
    )
    op.create_index("ix_tenants_domain", "tenants", ["domain"], unique=False)

    op.create_table(
        "organization_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_type", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False, server_default=sa.text("'UTC'")),
        sa.Column("working_hours_start", sa.Time(), nullable=False),
        sa.Column("working_hours_end", sa.Time(), nullable=False),
        sa.Column("booking_interval", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("advance_booking_days", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("cancellation_hours", sa.Integer(), nullable=False, server_default=sa.text("24")),
        sa.Column("custom_labels", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_organization_settings_tenant_id"),
    )


def downgrade() -> None:
    op.drop_table("organization_settings")
    op.drop_index("ix_tenants_domain", table_name="tenants")
    op.drop_table("tenants")
