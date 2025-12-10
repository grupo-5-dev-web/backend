"""Tests for deletion event consumers in resource service."""

import pytest
from uuid import uuid4
from app.deletion_consumers import handle_tenant_deleted
from app.models.resource import Resource, ResourceCategory
from app.core.database import SessionLocal


@pytest.mark.anyio
async def test_handle_tenant_deleted_deletes_resources_and_categories():
    """Verificar que tenant.deleted deleta todos os recursos e categorias do tenant."""
    db = SessionLocal()
    try:
        tenant_id = uuid4()
        
        # Criar 2 categorias
        category1 = ResourceCategory(
            tenant_id=tenant_id,
            name="Salas",
            type="physical",
        )
        category2 = ResourceCategory(
            tenant_id=tenant_id,
            name="Equipamentos",
            type="physical",
        )
        db.add_all([category1, category2])
        db.commit()
        db.refresh(category1)
        db.refresh(category2)
        
        # Criar 3 recursos
        resource1 = Resource(
            tenant_id=tenant_id,
            category_id=category1.id,
            name="Sala 101",
            status="active",
        )
        resource2 = Resource(
            tenant_id=tenant_id,
            category_id=category1.id,
            name="Sala 102",
            status="active",
        )
        resource3 = Resource(
            tenant_id=tenant_id,
            category_id=category2.id,
            name="Projetor A",
            status="active",
        )
        
        db.add_all([resource1, resource2, resource3])
        db.commit()
        
        resource_ids = [resource1.id, resource2.id, resource3.id]
        category_ids = [category1.id, category2.id]
        
        # Processar evento
        payload = {"tenant_id": str(tenant_id)}
        await handle_tenant_deleted("tenant.deleted", payload)

        # Verificar que TODOS os recursos foram deletados
        for resource_id in resource_ids:
            result = db.query(Resource).filter(Resource.id == resource_id).first()
            assert result is None, f"Resource {resource_id} deveria ter sido deletado"

        # Verificar que TODAS as categorias foram deletadas
        for category_id in category_ids:
            result = db.query(ResourceCategory).filter(ResourceCategory.id == category_id).first()
            assert result is None, f"Category {category_id} deveria ter sido deletada"
    finally:
        db.close()


@pytest.mark.anyio
async def test_handle_tenant_deleted_no_resources():
    """Verificar que tenant.deleted lida gracefully quando não há recursos."""
    payload = {"tenant_id": str(uuid4())}
    
    # Não deve lançar exceção
    await handle_tenant_deleted("tenant.deleted", payload)


@pytest.mark.anyio
async def test_handle_tenant_deleted_missing_tenant_id():
    """Verificar que tenant.deleted lida com payload sem tenant_id."""
    payload = {}
    
    # Não deve lançar exceção, apenas log warning
    await handle_tenant_deleted("tenant.deleted", payload)
