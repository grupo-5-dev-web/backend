"""Consumer para eventos de booking que envia webhooks."""

import asyncio
import logging
from typing import Dict, Any
from uuid import UUID
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared import EventConsumer, send_webhooks_for_event
from app.core.database import get_db, Base
from app.routers.crud import obter_webhooks_ativos_por_evento
from app.core.database import engine

logger = logging.getLogger(__name__)

# Cliente HTTP global para webhooks
_webhook_client: httpx.AsyncClient | None = None

# Session factory para criar sessões de banco de dados
SessionLocal = sessionmaker(bind=engine)


def get_webhook_client() -> httpx.AsyncClient:
    """Obtém ou cria o cliente HTTP para webhooks."""
    global _webhook_client
    if _webhook_client is None:
        _webhook_client = httpx.AsyncClient(timeout=10.0)
    return _webhook_client


async def handle_booking_created(event_type: str, payload: Dict[str, Any]) -> None:
    """Handler para evento booking.created."""
    # O tenant_id deve estar no payload (adicionado pelo booking service)
    tenant_id_str = payload.get("tenant_id")
    if not tenant_id_str:
        logger.warning("Evento booking.created sem tenant_id no payload")
        return
    
    try:
        tenant_id = UUID(tenant_id_str)
    except ValueError:
        logger.error(f"tenant_id inválido: {tenant_id_str}")
        return
    
    # Cria uma sessão de banco de dados para buscar webhooks
    db = SessionLocal()
    try:
        await send_webhooks_for_booking_event(db, event_type, payload, tenant_id)
    finally:
        db.close()


async def handle_booking_cancelled(event_type: str, payload: Dict[str, Any]) -> None:
    """Handler para evento booking.cancelled."""
    tenant_id_str = payload.get("tenant_id")
    if not tenant_id_str:
        logger.warning("Evento booking.cancelled sem tenant_id no payload")
        return
    
    try:
        tenant_id = UUID(tenant_id_str)
    except ValueError:
        logger.error(f"tenant_id inválido: {tenant_id_str}")
        return
    
    db = SessionLocal()
    try:
        await send_webhooks_for_booking_event(db, event_type, payload, tenant_id)
    finally:
        db.close()


async def handle_booking_updated(event_type: str, payload: Dict[str, Any]) -> None:
    """Handler para evento booking.updated."""
    tenant_id_str = payload.get("tenant_id")
    if not tenant_id_str:
        logger.warning("Evento booking.updated sem tenant_id no payload")
        return
    
    try:
        tenant_id = UUID(tenant_id_str)
    except ValueError:
        logger.error(f"tenant_id inválido: {tenant_id_str}")
        return
    
    db = SessionLocal()
    try:
        await send_webhooks_for_booking_event(db, event_type, payload, tenant_id)
    finally:
        db.close()


async def send_webhooks_for_booking_event(
    db: Session,
    event_type: str,
    payload: Dict[str, Any],
    tenant_id: UUID,
) -> None:
    """Envia webhooks para um evento de booking.
    
    Esta função deve ser chamada com uma sessão de banco de dados ativa.
    """
    # Obtém webhooks ativos para este evento
    webhooks = obter_webhooks_ativos_por_evento(db, tenant_id, event_type)
    
    if not webhooks:
        logger.debug(f"Nenhum webhook ativo para evento {event_type} do tenant {tenant_id}")
        return
    
    # Converte webhooks para formato esperado por send_webhooks_for_event
    webhook_list = [
        {
            "id": wh.id,
            "url": wh.url,
            "events": wh.events,
            "secret": wh.secret,
            "tenant_id": wh.tenant_id,
        }
        for wh in webhooks
    ]
    
    # Envia webhooks
    client = get_webhook_client()
    results = await send_webhooks_for_event(
        client,
        webhook_list,
        event_type,
        payload,
        tenant_id,
    )
    
    # Log dos resultados
    for result in results:
        if result["success"]:
            logger.info(f"Webhook {result['webhook_id']} enviado com sucesso")
        else:
            logger.warning(f"Falha ao enviar webhook {result['webhook_id']}: {result.get('error')}")

