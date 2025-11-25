from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from app.models.user import User
from app.schemas.user_schema import UserCreate, UserUpdate


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: Optional[str]) -> Optional[str]:
    if not plain_password:
        return None
    return pwd_context.hash(plain_password)


def verify_password(plain_password: Optional[str], password_hash: Optional[str]) -> bool:
    if not plain_password or not password_hash:
        return False
    return pwd_context.verify(plain_password, password_hash)


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
        update_data["permissions"] = update_data["permissions"].model_dump()
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


def deactivate_user(db: Session, user_id: UUID) -> Optional[User]:
    user = get_user(db, user_id)
    if not user:
        return None

    user.is_active = False
    db.commit()
    db.refresh(user)
    return user
