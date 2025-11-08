from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.tenant_schema import TenantCreate, TenantOut
from . import crud, validators

router = APIRouter()

@router.post("/", response_model=TenantOut)
def criar_tenant(tenant: TenantCreate, db: Session = Depends(get_db)):
    validators.validar_dominio_unico(db, tenant.dominio)
    return crud.criar_tenant(db, tenant)

@router.get("/", response_model=list[TenantOut])
def listar_tenants(db: Session = Depends(get_db)):
    return crud.listar_tenants(db)

@router.get("/{tenant_id}", response_model=TenantOut)
def buscar_tenant(tenant_id: int, db: Session = Depends(get_db)):
    tenant = crud.buscar_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return tenant

@router.delete("/{tenant_id}")
def deletar_tenant(tenant_id: int, db: Session = Depends(get_db)):
    tenant = crud.deletar_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return {"detail": "Tenant removido com sucesso"}
