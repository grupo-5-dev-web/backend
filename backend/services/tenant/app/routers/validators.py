from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from app.models.tenant import Tenant

def validar_dominio_unico(db: Session, dominio: str, tenant_id: UUID | None = None):
    query = db.query(Tenant).filter(Tenant.domain == dominio)
    if tenant_id:
        query = query.filter(Tenant.id != tenant_id)

    existente = query.first()
    if existente:
        raise HTTPException(status_code=400, detail="Domínio já cadastrado.")
