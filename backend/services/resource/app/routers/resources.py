from datetime import date
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.resource_schema import (
    ResourceAvailabilityResponse,
    ResourceCreate,
    ResourceOut,
    ResourceUpdate,
)
from app.services.availability import compute_availability
from . import crud

router = APIRouter(prefix="/resources", tags=["Resources"])


@router.post("/", response_model=ResourceOut, status_code=status.HTTP_201_CREATED)
def criar_recurso(recurso: ResourceCreate, db: Session = Depends(get_db)):
    categoria = crud.buscar_categoria(db, recurso.category_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    return crud.criar_recurso(db, recurso)


@router.get("/", response_model=List[ResourceOut])
def listar_recursos(
    tenant_id: Optional[UUID] = Query(default=None),
    category_id: Optional[UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    return crud.listar_recursos(db, tenant_id, category_id, status, search)


@router.get("/{recurso_id}", response_model=ResourceOut)
def obter_recurso(recurso_id: UUID, db: Session = Depends(get_db)):
    recurso = crud.buscar_recurso(db, recurso_id)
    if not recurso:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    return recurso


@router.put("/{recurso_id}", response_model=ResourceOut)
def atualizar_recurso(
    recurso_id: UUID,
    recurso_update: ResourceUpdate,
    db: Session = Depends(get_db),
):
    recurso = crud.atualizar_recurso(db, recurso_id, recurso_update)
    if not recurso:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    return recurso


@router.delete("/{recurso_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_recurso(recurso_id: UUID, db: Session = Depends(get_db)):
    recurso = crud.deletar_recurso(db, recurso_id)
    if not recurso:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    return None


@router.get("/{recurso_id}/availability", response_model=ResourceAvailabilityResponse)
def consultar_disponibilidade(
    recurso_id: UUID,
    request: Request,
    data: str = Query(..., description="Data da consulta no formato YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    try:
        target_date = date.fromisoformat(data)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Data inválida. Use o formato YYYY-MM-DD.") from exc

    result = compute_availability(
        app_state=request.app.state,
        db_session=db,
        resource_id=recurso_id,
        target_date=target_date,
    )
    return result
