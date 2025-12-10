from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, Form
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.user_schema import UserCreate, UserOut, UserUpdate
from app.services.tenant_validator import validar_tenant_existe
from app.core.auth_dependencies import get_current_user
from . import crud, validators
from app.models.user import User
from app.core.security import criar_token_jwt, verify_password

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/login")
def login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos")

    token = criar_token_jwt(user_id=user.id, tenant_id=user.tenant_id, user_type=user.user_type,)

    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, request: Request, db: Session = Depends(get_db)):

    await validar_tenant_existe(
        request.app.state.tenant_service_url,
        str(payload.tenant_id)
    )

    validators.ensure_unique_email(db, payload.tenant_id, payload.email)

    try:
        return crud.create_user(db, payload)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Erro ao criar usuário")

@router.get("/", response_model=List[UserOut])
def list_users(
    tenant_id: UUID = Query(..., description="Identificador do tenant"),
    user_type: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # só admin pode listar usuários
    if current_user.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas usuários admin podem listar usuários."
        )

    # admin só pode listar usuários do próprio tenant
    if tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é permitido listar usuários de outro tenant."
        )

    users = crud.list_users(db, tenant_id, user_type, is_active, search)

    if not users and is_active:
        raise HTTPException(status_code=404, detail="Não existem usuários ativos para este Tenant")
    if not users and user_type:
        raise HTTPException(status_code=404, detail="Não existem usuários deste tipo para este Tenant")
    if not users:
        raise HTTPException(status_code=404, detail="Não existem usuários para este Tenant")

    return users


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # pedindo o próprio usuário
    if user_id == current_user.id:
        return current_user

    # se NÃO é o próprio usuário e não é admin, n pode
    if current_user.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você só pode acessar os dados do seu próprio usuário."
        )

    # admin: pode buscar outro usuário, mas apenas do mesmo tenant
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para acessar usuários de outro tenant."
        )

    return user



@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Usuário alvo da atualização
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if current_user.user_type != "admin":
        # User comum só pode atualizar ele mesmo
        if user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você só pode atualizar os dados do seu próprio usuário."
            )
        tenant_para_validacao = current_user.tenant_id
    else:
        if user.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para atualizar usuários de outro tenant."
            )
        tenant_para_validacao = user.tenant_id

    if payload.email:
        validators.ensure_unique_email(
            db,
            tenant_para_validacao,
            payload.email,
            user_id=user_id,
        )

    try:
        updated_user = crud.update_user(db, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Erro ao atualizar usuário")

    return updated_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if current_user.user_type != "admin":
        # user comum só pode deletar a si mesmo
        if user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você só pode deletar o seu próprio usuário."
            )
    else:
        # admin só pode deletar usuários do mesmo tenant
        if user.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para deletar usuários de outro tenant."
            )

    deleted = crud.delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    return None
