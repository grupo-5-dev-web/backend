from uuid import UUID
from sqlalchemy.orm import Session
from app.models.tenant import Tenant, OrganizationSettings
from app.schemas.tenant_schema import (
    TenantCreate,
    TenantUpdate,
    OrganizationSettingsUpdate,
)

def criar_tenant(db: Session, tenant_data: TenantCreate) -> Tenant:
    novo_tenant = Tenant(
        name=tenant_data.name,
        domain=tenant_data.domain,
        logo_url=str(tenant_data.logo_url),
        theme_primary_color=tenant_data.theme_primary_color,
        plan=tenant_data.plan,
        is_active=tenant_data.is_active,
    )

    settings = OrganizationSettings(
        business_type=tenant_data.settings.business_type,
        timezone=tenant_data.settings.timezone,
        working_hours_start=tenant_data.settings.working_hours_start,
        working_hours_end=tenant_data.settings.working_hours_end,
        booking_interval=tenant_data.settings.booking_interval,
        advance_booking_days=tenant_data.settings.advance_booking_days,
        cancellation_hours=tenant_data.settings.cancellation_hours,
        custom_labels=tenant_data.settings.custom_labels.model_dump(),
    )

    novo_tenant.settings = settings

    db.add(novo_tenant)
    db.commit()
    db.refresh(novo_tenant)
    return novo_tenant

def listar_tenants(db: Session):
    return db.query(Tenant).all()

def buscar_tenant(db: Session, tenant_id: UUID):
    return (
        db.query(Tenant)
        .filter(Tenant.id == tenant_id)
        .first()
    )

def atualizar_tenant(db: Session, tenant_id: UUID, tenant_update: TenantUpdate):
    tenant = buscar_tenant(db, tenant_id)
    if not tenant:
        return None

    update_data = tenant_update.model_dump(exclude_unset=True)
    if "logo_url" in update_data and update_data["logo_url"] is not None:
        update_data["logo_url"] = str(update_data["logo_url"])

    for field, value in update_data.items():
        setattr(tenant, field, value)

    db.commit()
    db.refresh(tenant)
    return tenant


def deletar_tenant(db: Session, tenant_id: UUID, publisher=None):
    tenant = buscar_tenant(db, tenant_id)
    if not tenant:
        return None

    # Publicar evento ANTES de deletar para outros serviços reagirem
    if publisher:
        payload = {
            "tenant_id": str(tenant_id),
        }
        publisher.publish("tenant.deleted", payload)

    db.delete(tenant)
    db.commit()
    return tenant


def obter_configuracoes(db: Session, tenant_id: UUID):
    return (
        db.query(OrganizationSettings)
        .filter(OrganizationSettings.tenant_id == tenant_id)
        .first()
    )


def atualizar_configuracoes(
    db: Session,
    tenant_id: UUID,
    config_update: OrganizationSettingsUpdate,
):
    configuracoes = obter_configuracoes(db, tenant_id)
    if not configuracoes:
        return None

    update_data = config_update.model_dump(exclude_unset=True)
    if "custom_labels" in update_data and update_data["custom_labels"] is not None:
        update_data["custom_labels"] = update_data["custom_labels"].model_dump()

    for field, value in update_data.items():
        setattr(configuracoes, field, value)

    db.commit()
    db.refresh(configuracoes)
    return configuracoes
