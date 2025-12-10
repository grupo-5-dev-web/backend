"""Event consumers for user service - handles deletion cascades."""

import logging
from typing import Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)


async def handle_tenant_deleted(payload: Dict[str, Any]) -> None:
    """
    Handler para evento tenant.deleted.
    Deleta TODOS os usuários daquele tenant.
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
        # Buscar todos os usuários do tenant
        users = db.query(User).filter(User.tenant_id == tenant_id).all()
        
        if not users:
            logger.info(f"Nenhum usuário encontrado para tenant_id={tenant_id}")
            return
        
        # Deletar todos os usuários
        for user in users:
            db.delete(user)
        
        db.commit()
        logger.info(f"Deletados {len(users)} usuários do tenant_id={tenant_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao processar tenant.deleted para tenant_id={tenant_id}: {e}")
        raise
    finally:
        db.close()
