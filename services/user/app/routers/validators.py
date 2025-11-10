from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.user import User


def ensure_unique_email(db: Session, tenant_id: UUID, email: str, user_id: UUID | None = None) -> None:
    query = db.query(User).filter(User.tenant_id == tenant_id, User.email == email)
    if user_id:
        query = query.filter(User.id != user_id)

    if query.first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado para este tenant")
