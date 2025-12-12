"""Router para gerenciamento de webhooks."""

from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_dependencies import get_current_token, TokenPayload
from app.schemas.webhook_schema import (
    WebhookCreate,
    WebhookUpdate,
    WebhookOut,
)
from . import crud

router = APIRouter(tags=["Webhooks"])


@router.post("/tenants/{tenant_id}/webhooks", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
def criar_webhook(
    tenant_id: UUID,
    webhook: WebhookCreate,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    """Cria um novo webhook para o tenant."""
    # Só admin pode criar webhooks
    if current_token.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente administradores podem criar webhooks",
        )
    
    # Admin só pode criar webhooks para o próprio tenant
    if current_token.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para criar webhooks para este tenant",
        )
    
    # Verifica se o tenant existe
    tenant = crud.buscar_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    
    return crud.criar_webhook(db, tenant_id, webhook)


@router.get("/tenants/{tenant_id}/webhooks", response_model=List[WebhookOut])
def listar_webhooks(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    """Lista todos os webhooks do tenant."""
    # Qualquer usuário autenticado pode listar webhooks do próprio tenant
    if current_token.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para listar webhooks deste tenant",
        )
    
    return crud.listar_webhooks(db, tenant_id)


@router.get("/tenants/{tenant_id}/webhooks/{webhook_id}", response_model=WebhookOut)
def buscar_webhook(
    tenant_id: UUID,
    webhook_id: UUID,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    """Busca um webhook específico."""
    # Qualquer usuário autenticado pode buscar webhooks do próprio tenant
    if current_token.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para buscar webhooks deste tenant",
        )
    
    webhook = crud.buscar_webhook(db, tenant_id, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook não encontrado")
    return webhook


@router.put("/tenants/{tenant_id}/webhooks/{webhook_id}", response_model=WebhookOut)
def atualizar_webhook(
    tenant_id: UUID,
    webhook_id: UUID,
    webhook_update: WebhookUpdate,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    """Atualiza um webhook existente."""
    # Só admin pode atualizar webhooks
    if current_token.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente administradores podem atualizar webhooks",
        )
    
    # Admin só pode atualizar webhooks do próprio tenant
    if current_token.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para atualizar webhooks deste tenant",
        )
    
    webhook = crud.atualizar_webhook(db, tenant_id, webhook_id, webhook_update)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook não encontrado")
    return webhook


@router.delete("/tenants/{tenant_id}/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_webhook(
    tenant_id: UUID,
    webhook_id: UUID,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    """Deleta um webhook."""
    # Só admin pode deletar webhooks
    if current_token.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente administradores podem deletar webhooks",
        )
    
    # Admin só pode deletar webhooks do próprio tenant
    if current_token.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para deletar webhooks deste tenant",
        )
    
    webhook = crud.deletar_webhook(db, tenant_id, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook não encontrado")
    return None

