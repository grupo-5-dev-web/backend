"""Event consumers for booking service - handles deletion cascades."""

import logging
from typing import Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.booking import Booking, BookingStatus

logger = logging.getLogger(__name__)


async def handle_resource_deleted(payload: Dict[str, Any]) -> None:
    """
    Handler para evento resource.deleted.
    Cancela todas as reservas ativas daquele recurso.
    """
    resource_id = payload.get("resource_id")
    
    if not resource_id:
        logger.warning("Evento resource.deleted sem resource_id")
        return
    
    # Converter string para UUID
    if isinstance(resource_id, str):
        resource_id = UUID(resource_id)
    
    db: Session = SessionLocal()
    try:
        # Buscar todas as reservas ativas (pendente/confirmado) do recurso
        bookings = (
            db.query(Booking)
            .filter(Booking.resource_id == resource_id)
            .filter(Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]))
            .all()
        )
        
        if not bookings:
            logger.info(f"Nenhuma reserva ativa encontrada para resource_id={resource_id}")
            return
        
        # Cancelar todas as reservas
        for booking in bookings:
            booking.status = BookingStatus.CANCELLED
            booking.cancellation_reason = f"Recurso deletado (resource_id={resource_id})"
        
        db.commit()
        logger.info(f"Canceladas {len(bookings)} reservas do resource_id={resource_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao processar resource.deleted para resource_id={resource_id}: {e}")
        raise
    finally:
        db.close()


async def handle_user_deleted(payload: Dict[str, Any]) -> None:
    """
    Handler para evento user.deleted.
    Cancela todas as reservas do usuário.
    """
    user_id = payload.get("user_id")
    
    if not user_id:
        logger.warning("Evento user.deleted sem user_id")
        return
    
    # Converter string para UUID
    if isinstance(user_id, str):
        user_id = UUID(user_id)
    
    db: Session = SessionLocal()
    try:
        # Buscar todas as reservas ativas do usuário
        bookings = (
            db.query(Booking)
            .filter(Booking.user_id == user_id)
            .filter(Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]))
            .all()
        )
        
        if not bookings:
            logger.info(f"Nenhuma reserva ativa encontrada para user_id={user_id}")
            return
        
        # Cancelar todas as reservas
        for booking in bookings:
            booking.status = BookingStatus.CANCELLED
            booking.cancellation_reason = f"Usuário deletado (user_id={user_id})"
        
        db.commit()
        logger.info(f"Canceladas {len(bookings)} reservas do user_id={user_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao processar user.deleted para user_id={user_id}: {e}")
        raise
    finally:
        db.close()


async def handle_tenant_deleted(payload: Dict[str, Any]) -> None:
    """
    Handler para evento tenant.deleted.
    Deleta TODAS as reservas do tenant (cascata total).
    """
    tenant_id = payload.get("tenant_id")
    
    if not tenant_id:
        logger.warning("Evento tenant.deleted sem tenant_id")
        return
    
    # Converter string para UUID
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)
    
    db: Session = SessionLocal()
    try:
        # Buscar TODAS as reservas do tenant (qualquer status)
        bookings = db.query(Booking).filter(Booking.tenant_id == tenant_id).all()
        
        if not bookings:
            logger.info(f"Nenhuma reserva encontrada para tenant_id={tenant_id}")
            return
        
        # Deletar todas as reservas
        for booking in bookings:
            db.delete(booking)
        
        db.commit()
        logger.info(f"Deletadas {len(bookings)} reservas do tenant_id={tenant_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao processar tenant.deleted para tenant_id={tenant_id}: {e}")
        raise
    finally:
        db.close()
