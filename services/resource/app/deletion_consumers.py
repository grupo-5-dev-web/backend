"""Event consumers for resource service - handles deletion cascades."""

import logging
from typing import Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.resource import Resource, ResourceCategory

logger = logging.getLogger(__name__)


async def handle_tenant_deleted(payload: Dict[str, Any]) -> None:
    """
    Handler para evento tenant.deleted.
    Deleta TODOS os recursos e categorias daquele tenant.
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
        # Buscar todos os recursos do tenant
        resources = db.query(Resource).filter(Resource.tenant_id == tenant_id).all()
        
        # Deletar todos os recursos PRIMEIRO (eles têm FK para categorias)
        for resource in resources:
            db.delete(resource)
        
        # Buscar todas as categorias do tenant
        categories = db.query(ResourceCategory).filter(ResourceCategory.tenant_id == tenant_id).all()
        
        # Deletar todas as categorias DEPOIS (para evitar violação de FK)
        for category in categories:
            db.delete(category)
        
        db.commit()
        logger.info(f"Deletados {len(resources)} recursos e {len(categories)} categorias do tenant_id={tenant_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao processar tenant.deleted para tenant_id={tenant_id}: {e}")
        raise
    finally:
        db.close()
