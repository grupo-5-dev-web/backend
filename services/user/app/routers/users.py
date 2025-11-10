from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.user_schema import UserCreate, UserOut, UserUpdate
from . import crud, validators

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(payload: UserCreate, db: Session = Depends(get_db)):
    validators.ensure_unique_email(db, payload.tenant_id, payload.email)
    try:
        return crud.create_user(db, payload)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Erro ao criar usuário")


@router.get("/", response_model=List[UserOut])
def list_users_endpoint(
    tenant_id: UUID = Query(..., description="Identificador do tenant"),
    user_type: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    return crud.list_users(db, tenant_id, user_type, is_active, search)


@router.get("/{user_id}", response_model=UserOut)
def get_user_endpoint(user_id: UUID, db: Session = Depends(get_db)):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user_endpoint(user_id: UUID, payload: UserUpdate, db: Session = Depends(get_db)):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if payload.email:
        validators.ensure_unique_email(db, user.tenant_id, payload.email, user_id=user_id)

    try:
        updated_user = crud.update_user(db, user_id, payload)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Erro ao atualizar usuário")

    return updated_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user_endpoint(user_id: UUID, db: Session = Depends(get_db)):
    user = crud.deactivate_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return None
