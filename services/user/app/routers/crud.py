from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from app.schemas.user_schema import UserCreate, UserUpdate


def hash_password(plain_password: Optional[str]) -> Optional[str]:
    # TODO: substituir por hash seguro (ex: passlib/bcrypt)
    if not plain_password:
        return None
    return plain_password


def create_user(db: Session, payload: UserCreate) -> User:
    user = User(
        tenant_id=payload.tenant_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        user_type=payload.user_type,
        department=payload.department,
        is_active=payload.is_active,
        permissions=payload.permissions.model_dump(),
        profile_metadata=payload.profile_metadata,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(user)
    return user


def list_users(
    db: Session,
    tenant_id: Optional[UUID] = None,
    user_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
):
    query = db.query(User)
    if tenant_id:
        query = query.filter(User.tenant_id == tenant_id)
    if user_type:
        query = query.filter(User.user_type == user_type)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(User.name.ilike(like_pattern))
    return query.order_by(User.name.asc()).all()


def get_user(db: Session, user_id: UUID) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def update_user(db: Session, user_id: UUID, payload: UserUpdate) -> Optional[User]:
    user = get_user(db, user_id)
    if not user:
        return None

    update_data = payload.model_dump(exclude_unset=True)

    if "permissions" in update_data and update_data["permissions"] is not None:
        # Handle both Pydantic object and dict (already serialized)
        if hasattr(update_data["permissions"], "model_dump"):
            update_data["permissions"] = update_data["permissions"].model_dump()
        # else: already a dict, keep as-is
    if "profile_metadata" in update_data and update_data["profile_metadata"] is None:
        update_data["profile_metadata"] = {}
    if "password" in update_data:
        user.password_hash = hash_password(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: UUID, publisher=None) -> Optional[User]:
    user = get_user(db, user_id)
    if not user:
        return None

    # Publicar evento ANTES de deletar para outros serviços reagirem
    if publisher:
        payload = {
            "user_id": str(user_id),
            "tenant_id": str(user.tenant_id),
        }
        publisher.publish("user.deleted", payload)

    db.delete(user)
    db.commit()

    return user