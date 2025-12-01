from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
    status_code=status.HTTP_201_CREATED
)
async def criar_categoria(
    categoria: ResourceCategoryCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    tenant_service_url = request.app.state.tenant_service_url

    # Valida Tenant — com bypass automático em pytest
    await validar_tenant_existe(
        tenant_service_url,
        str(categoria.tenant_id)
    )

    return crud.criar_categoria(db, categoria)


@router.get("/", response_model=List[ResourceCategoryOut])
def listar_categorias(
    tenant_id: Optional[UUID] = Query(default=None, description="Tenant a filtrar"),
    db: Session = Depends(get_db),
):
    categorias = crud.listar_categorias(db, tenant_id)

    if not categorias:
        raise HTTPException(
            status_code=404, 
            detail="Não existem categorias para este Tenant ou ele não existe"
        )

    return categorias


@router.get("/{categoria_id}", response_model=ResourceCategoryOut)
def obter_categoria(
    categoria_id: UUID,
    db: Session = Depends(get_db)
):
    categoria = crud.buscar_categoria(db, categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    return categoria


@router.put("/{categoria_id}", response_model=ResourceCategoryOut)
def atualizar_categoria(
    categoria_id: UUID,
    categoria_update: ResourceCategoryUpdate,
    db: Session = Depends(get_db),
):
    categoria = crud.atualizar_categoria(db, categoria_id, categoria_update)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    return categoria


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_categoria(
    categoria_id: UUID,
    db: Session = Depends(get_db)
):
    categoria = crud.deletar_categoria(db, categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    return None
