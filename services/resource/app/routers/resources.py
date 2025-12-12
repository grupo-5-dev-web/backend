from datetime import date
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.resource_schema import (ResourceAvailabilityResponse,ResourceCreate,ResourceOut,ResourceUpdate)
from app.services.availability import compute_availability
from app.services.tenant_validator import validar_tenant_existe
from . import crud
from app.core.auth_dependencies import get_current_token, TokenPayload, oauth2_scheme

router = APIRouter(tags=["Resources"])


@router.post(
    "/", 
    response_model=ResourceOut, 
    status_code=status.HTTP_201_CREATED
)
async def criar_recurso(
    recurso: ResourceCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    # Só ADMIN pode criar recurso e precisa ser do mesmo tenant
    if current_token.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem criar recursos.",
        )

    if recurso.tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para criar recursos para outro tenant.",
        )

    tenant_service_url = request.app.state.tenant_service_url

    await validar_tenant_existe(
        tenant_service_url,
        str(recurso.tenant_id),
    )

    categoria = crud.buscar_categoria(db, recurso.category_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    if categoria.tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não pode usar uma categoria de outro tenant.",
        )

    return crud.criar_recurso(db, recurso)


@router.get("/", response_model=List[ResourceOut])
def listar_recursos(
    tenant_id: Optional[UUID] = Query(default=None),
    category_id: Optional[UUID] = Query(default=None),
    status_param: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):

    if tenant_id is None:
        tenant_id = current_token.tenant_id
    else:
        if tenant_id != current_token.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para listar recursos de outro tenant.",
            )

    recursos = crud.listar_recursos(db, tenant_id, category_id, status_param, search)

    if not recursos and category_id:
        raise HTTPException(
            status_code=404,
            detail="Não foram encontrados Recursos nesta categoria",
        )
    if not recursos and tenant_id:
        raise HTTPException(
            status_code=404,
            detail="Não foram encontrados Recursos neste Tenant",
        )
    if not recursos:
        raise HTTPException(
            status_code=404,
            detail="Não foram encontrados Recursos",
        )

    return recursos


@router.get("/{recurso_id}", response_model=ResourceOut)
def obter_recurso(
    recurso_id: UUID,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):

    recurso = crud.buscar_recurso(db, recurso_id)
    if not recurso:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")

    if recurso.tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para acessar este recurso.",
        )

    return recurso


@router.put("/{recurso_id}", response_model=ResourceOut)
def atualizar_recurso(
    recurso_id: UUID,
    recurso_update: ResourceUpdate,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    
    recurso_atual = crud.buscar_recurso(db, recurso_id)
    if not recurso_atual:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")

    if current_token.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem atualizar recursos.",
        )

    if recurso_atual.tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para atualizar recursos de outro tenant.",
        )

    recurso = crud.atualizar_recurso(db, recurso_id, recurso_update)
    if not recurso:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")

    return recurso


@router.delete("/{recurso_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_recurso(
    recurso_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):

    recurso_atual = crud.buscar_recurso(db, recurso_id)
    if not recurso_atual:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")

    if current_token.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem deletar recursos.",
        )

    if recurso_atual.tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para deletar recursos de outro tenant.",
        )

    recurso = crud.deletar_recurso(db, recurso_id)
    if not recurso:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    
    # Publicar evento de deleção de recurso
    publisher = request.app.state.event_publisher
    if publisher:
        publisher.publish("resource.deleted", {"resource_id": str(recurso_id)})
    
    return None


@router.get("/{recurso_id}/availability", response_model=ResourceAvailabilityResponse)
def consultar_disponibilidade(
    recurso_id: UUID,
    request: Request,
    data: str = Query(..., description="Data da consulta no formato YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
    raw_token: str = Depends(oauth2_scheme),
):
    recurso = crud.buscar_recurso(db, recurso_id)
    if not recurso:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")

    if recurso.tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para consultar disponibilidade deste recurso.",
        )

    try:
        target_date = date.fromisoformat(data)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Data inválida. Use o formato YYYY-MM-DD.",
        ) from exc

    result = compute_availability(
        app_state=request.app.state,
        db_session=db,
        resource_id=recurso_id,
        target_date=target_date,
        auth_token=raw_token,
    )
    return result
