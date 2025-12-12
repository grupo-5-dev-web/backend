from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.resource_schema import (
    ResourceCategoryCreate,
    ResourceCategoryOut,
    ResourceCategoryUpdate,
)
from . import crud

router = APIRouter(prefix="/categories", tags=["Resource Categories"])


@router.post("/", response_model=ResourceCategoryOut, status_code=status.HTTP_201_CREATED)
def criar_categoria(categoria: ResourceCategoryCreate, db: Session = Depends(get_db)):
    return crud.criar_categoria(db, categoria)


@router.get("/", response_model=List[ResourceCategoryOut])
def listar_categorias(
    tenant_id: Optional[UUID] = Query(default=None, description="Tenant a filtrar"),
    db: Session = Depends(get_db),
):
    return crud.listar_categorias(db, tenant_id)


@router.get("/{categoria_id}", response_model=ResourceCategoryOut)
def obter_categoria(categoria_id: UUID, db: Session = Depends(get_db)):
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
def arquivar_categoria(categoria_id: UUID, db: Session = Depends(get_db)):
    categoria = crud.buscar_categoria(db, categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    categoria.is_active = False
    db.commit()
    return None
