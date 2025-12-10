"""Tests for deletion event consumers in user service."""

import pytest
from uuid import uuid4
from app.deletion_consumers import handle_tenant_deleted
from app.models.user import User
from app.core.database import SessionLocal


@pytest.mark.anyio
async def test_handle_tenant_deleted_deletes_all_users():
    """Verificar que tenant.deleted deleta todos os usuários do tenant."""
    db = SessionLocal()
    try:
        tenant_id = uuid4()
        
        # Criar 3 usuários
        user1 = User(
            tenant_id=tenant_id,
            name="João Silva",
            email="joao@example.com",
            user_type="admin",
        )
        user2 = User(
            tenant_id=tenant_id,
            name="Maria Santos",
            email="maria@example.com",
            user_type="user",
        )
        user3 = User(
            tenant_id=tenant_id,
            name="Pedro Costa",
            email="pedro@example.com",
            user_type="user",
            is_active=False,
        )
        
        db.add_all([user1, user2, user3])
        db.commit()
        
        user_ids = [user1.id, user2.id, user3.id]
        
        # Processar evento
        payload = {"tenant_id": str(tenant_id)}
        await handle_tenant_deleted(payload)
        
        # Verificar que TODOS os usuários foram deletados
        for user_id in user_ids:
            result = db.query(User).filter(User.id == user_id).first()
            assert result is None, f"User {user_id} deveria ter sido deletado"
    
    finally:
        db.close()


@pytest.mark.anyio
async def test_handle_tenant_deleted_no_users():
    """Verificar que tenant.deleted lida gracefully quando não há usuários."""
    payload = {"tenant_id": str(uuid4())}
    
    # Não deve lançar exceção
    await handle_tenant_deleted(payload)


@pytest.mark.anyio
async def test_handle_tenant_deleted_missing_tenant_id():
    """Verificar que tenant.deleted lida com payload sem tenant_id."""
    payload = {}
    
    # Não deve lançar exceção, apenas log warning
    await handle_tenant_deleted(payload)
