from sqlalchemy.orm import Session
from app.models.tenant import Tenant
from app.schemas.tenant_schema import TenantCreate

def criar_tenant(db: Session, tenant_data: TenantCreate):
    novo = Tenant(
        nome=tenant_data.nome,
        dominio=tenant_data.dominio,
        logo=tenant_data.logo,
        tema_cor=tenant_data.tema_cor,
        plano=tenant_data.plano
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

def listar_tenants(db: Session):
    return db.query(Tenant).all()

def buscar_tenant(db: Session, tenant_id: int):
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()

def deletar_tenant(db: Session, tenant_id: int):
    tenant = buscar_tenant(db, tenant_id)
    if tenant:
        db.delete(tenant)
        db.commit()
    return tenant
