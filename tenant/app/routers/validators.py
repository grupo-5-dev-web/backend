from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.tenant import Tenant

def validar_dominio_unico(db: Session, dominio: str):
    existente = db.query(Tenant).filter(Tenant.dominio == dominio).first()
    if existente:
        raise HTTPException(status_code=400, detail="Domínio já cadastrado.")
