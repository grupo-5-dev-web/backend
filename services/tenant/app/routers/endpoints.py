from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.tenant_schema import (
    TenantCreate,
    TenantOut,
    TenantUpdate,
    OrganizationSettingsOut,
    OrganizationSettingsUpdate,
)
from . import crud, validators

router = APIRouter(tags=["Tenants"])

@router.post("/", response_model=TenantOut)
def criar_tenant(tenant: TenantCreate, db: Session = Depends(get_db)):
    validators.validar_dominio_unico(db, tenant.domain)
    return crud.criar_tenant(db, tenant)

@router.get("/", response_model=List[TenantOut])
def listar_tenants(db: Session = Depends(get_db)):
    return crud.listar_tenants(db)

@router.get("/{tenant_id}", response_model=TenantOut)
def buscar_tenant(tenant_id: UUID, db: Session = Depends(get_db)):
    tenant = crud.buscar_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return tenant

@router.put("/{tenant_id}", response_model=TenantOut)
def atualizar_tenant(tenant_id: UUID, tenant_update: TenantUpdate, db: Session = Depends(get_db)):
    if tenant_update.domain:
        validators.validar_dominio_unico(db, tenant_update.domain, tenant_id)

    tenant = crud.atualizar_tenant(db, tenant_id, tenant_update)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_tenant(tenant_id: UUID, db: Session = Depends(get_db)):
    tenant = crud.deletar_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return None


@router.get("/{tenant_id}/settings", response_model=OrganizationSettingsOut)
def obter_configuracoes(tenant_id: UUID, db: Session = Depends(get_db)):
    configuracoes = crud.obter_configuracoes(db, tenant_id)
    if not configuracoes:
        raise HTTPException(status_code=404, detail="Configurações não encontradas")
    return configuracoes


@router.put("/{tenant_id}/settings", response_model=OrganizationSettingsOut)
def atualizar_configuracoes(
    tenant_id: UUID,
    config_update: OrganizationSettingsUpdate,
    db: Session = Depends(get_db),
):
    configuracoes = crud.atualizar_configuracoes(db, tenant_id, config_update)
    if not configuracoes:
        raise HTTPException(status_code=404, detail="Configurações não encontradas")
    return configuracoes
