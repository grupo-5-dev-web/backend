from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from app.core.auth_dependencies import get_current_token, TokenPayload
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.resource_schema import (
    ResourceCategoryCreate,
    ResourceCategoryOut,
    ResourceCategoryUpdate,
)
from app.services.tenant_validator import validar_tenant_existe
from . import crud

router = APIRouter(tags=["Resource Categories"])

@router.post(
    "/",
    response_model=ResourceCategoryOut,
    status_code=status.HTTP_201_CREATED,
)
async def criar_categoria(
    categoria: ResourceCategoryCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    # só admin pode criar categoria
    if current_token.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente administradores podem criar categorias",
        )

    # categoria só pode ser criada no mesmo tenant do usuário
    if current_token.tenant_id != categoria.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não pode criar categorias para outro tenant",
        )

    tenant_service_url = request.app.state.tenant_service_url

    await validar_tenant_existe(
        tenant_service_url,
        str(categoria.tenant_id),
    )

    return crud.criar_categoria(db, categoria)


@router.get("/", response_model=List[ResourceCategoryOut])
def listar_categorias(
    tenant_id: Optional[UUID] = Query(
        default=None,
        description="Tenant a filtrar",
    ),
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    # só admin pode listar categorias
    if current_token.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente administradores podem listar categorias",
        )

    # se não vier tenant_id, assume o tenant do usuário logado
    if tenant_id is None:
        tenant_id = current_token.tenant_id
    # se vier tenant_id diferente, bloqueia
    elif tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para listar categorias de outro tenant",
        )

    categorias = crud.listar_categorias(db, tenant_id)

    if not categorias:
        raise HTTPException(
            status_code=404,
            detail="Não existem categorias para este Tenant ou ele não existe",
        )

    return categorias


@router.get("/{categoria_id}", response_model=ResourceCategoryOut)
def obter_categoria(
    categoria_id: UUID,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    categoria = crud.buscar_categoria(db, categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    # admin ou user pode ver, mas só se for do mesmo tenant
    if categoria.tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para acessar esta categoria",
        )

    return categoria


@router.put("/{categoria_id}", response_model=ResourceCategoryOut)
def atualizar_categoria(
    categoria_id: UUID,
    categoria_update: ResourceCategoryUpdate,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    # Só admin pode atualizar categoria
    if current_token.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente administradores podem atualizar categorias",
        )

    # Primeiro busca para validar tenant
    categoria_existente = crud.buscar_categoria(db, categoria_id)
    if not categoria_existente:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    if categoria_existente.tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para atualizar esta categoria",
        )

    categoria = crud.atualizar_categoria(db, categoria_id, categoria_update)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    return categoria


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_categoria(
    categoria_id: UUID,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    # Só admin pode deletar categoria
    if current_token.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente administradores podem deletar categorias",
        )

    categoria_existente = crud.buscar_categoria(db, categoria_id)
    if not categoria_existente:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    if categoria_existente.tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para deletar esta categoria",
        )

    categoria = crud.deletar_categoria(db, categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    return None