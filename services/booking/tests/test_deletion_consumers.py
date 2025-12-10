"""Tests for deletion event consumers in booking service."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from app.consumers import handle_resource_deleted, handle_user_deleted, handle_tenant_deleted
from app.models.booking import Booking, BookingStatus
from app.core.database import SessionLocal


@pytest.mark.anyio
async def test_handle_resource_deleted_cancels_bookings():
    """Verificar que resource.deleted cancela todas as reservas ativas do recurso."""
    db = SessionLocal()
    
    tenant_id = uuid4()
    resource_id = uuid4()
    user_id = uuid4()
    
    # Criar 2 reservas ativas e 1 já cancelada
    booking1 = Booking(
        tenant_id=tenant_id,
        resource_id=resource_id,
        user_id=user_id,
        start_time=datetime(2025, 12, 15, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2025, 12, 15, 11, 0, 0, tzinfo=timezone.utc),
        status=BookingStatus.PENDING,
    )
    booking2 = Booking(
        tenant_id=tenant_id,
        resource_id=resource_id,
        user_id=user_id,
        start_time=datetime(2025, 12, 16, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2025, 12, 16, 11, 0, 0, tzinfo=timezone.utc),
        status=BookingStatus.CONFIRMED,
    )
    booking3 = Booking(
        tenant_id=tenant_id,
        resource_id=resource_id,
        user_id=user_id,
        start_time=datetime(2025, 12, 17, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2025, 12, 17, 11, 0, 0, tzinfo=timezone.utc),
        status=BookingStatus.CANCELLED,
    )
    
    db.add_all([booking1, booking2, booking3])
    db.commit()
    
    # Processar evento
    payload = {"resource_id": str(resource_id), "tenant_id": str(tenant_id)}
    await handle_resource_deleted(payload)
    
    # Verificar que apenas as ativas foram canceladas
    db.refresh(booking1)
    db.refresh(booking2)
    db.refresh(booking3)
    
    assert booking1.status == BookingStatus.CANCELLED
    assert "Recurso deletado" in booking1.cancellation_reason
    assert booking2.status == BookingStatus.CANCELLED
    assert "Recurso deletado" in booking2.cancellation_reason
    assert booking3.status == BookingStatus.CANCELLED  # já estava cancelada
    
    # Cleanup
    db.delete(booking1)
    db.delete(booking2)
    db.delete(booking3)
    db.commit()
    db.close()


@pytest.mark.anyio
async def test_handle_user_deleted_cancels_bookings():
    """Verificar que user.deleted cancela todas as reservas do usuário."""
    db = SessionLocal()
    
    tenant_id = uuid4()
    resource_id = uuid4()
    user_id = uuid4()
    
    # Criar 2 reservas ativas
    booking1 = Booking(
        tenant_id=tenant_id,
        resource_id=resource_id,
        user_id=user_id,
        start_time=datetime(2025, 12, 15, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2025, 12, 15, 11, 0, 0, tzinfo=timezone.utc),
        status=BookingStatus.PENDING,
    )
    booking2 = Booking(
        tenant_id=tenant_id,
        resource_id=uuid4(),  # recurso diferente
        user_id=user_id,
        start_time=datetime(2025, 12, 16, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2025, 12, 16, 11, 0, 0, tzinfo=timezone.utc),
        status=BookingStatus.CONFIRMED,
    )
    
    db.add_all([booking1, booking2])
    db.commit()
    
    # Processar evento
    payload = {"user_id": str(user_id), "tenant_id": str(tenant_id)}
    await handle_user_deleted(payload)
    
    # Verificar que foram canceladas
    db.refresh(booking1)
    db.refresh(booking2)
    
    assert booking1.status == BookingStatus.CANCELLED
    assert "Usuário deletado" in booking1.cancellation_reason
    assert booking2.status == BookingStatus.CANCELLED
    assert "Usuário deletado" in booking2.cancellation_reason
    
    # Cleanup
    db.delete(booking1)
    db.delete(booking2)
    db.commit()
    db.close()


@pytest.mark.anyio
async def test_handle_tenant_deleted_deletes_all_bookings():
    """Verificar que tenant.deleted deleta TODAS as reservas do tenant."""
    db = SessionLocal()
    
    tenant_id = uuid4()
    
    # Criar 3 reservas com status diferentes
    booking1 = Booking(
        tenant_id=tenant_id,
        resource_id=uuid4(),
        user_id=uuid4(),
        start_time=datetime(2025, 12, 15, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2025, 12, 15, 11, 0, 0, tzinfo=timezone.utc),
        status=BookingStatus.PENDING,
    )
    booking2 = Booking(
        tenant_id=tenant_id,
        resource_id=uuid4(),
        user_id=uuid4(),
        start_time=datetime(2025, 12, 16, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2025, 12, 16, 11, 0, 0, tzinfo=timezone.utc),
        status=BookingStatus.CONFIRMED,
    )
    booking3 = Booking(
        tenant_id=tenant_id,
        resource_id=uuid4(),
        user_id=uuid4(),
        start_time=datetime(2025, 12, 17, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2025, 12, 17, 11, 0, 0, tzinfo=timezone.utc),
        status=BookingStatus.CANCELLED,
    )
    
    db.add_all([booking1, booking2, booking3])
    db.commit()
    
    booking_ids = [booking1.id, booking2.id, booking3.id]
    
    # Processar evento
    payload = {"tenant_id": str(tenant_id)}
    await handle_tenant_deleted(payload)
    
    # Verificar que TODAS foram deletadas
    for booking_id in booking_ids:
        result = db.query(Booking).filter(Booking.id == booking_id).first()
        assert result is None, f"Booking {booking_id} deveria ter sido deletada"
    
    db.close()


@pytest.mark.anyio
async def test_handle_resource_deleted_no_bookings():
    """Verificar que resource.deleted lida gracefully quando não há reservas."""
    payload = {"resource_id": str(uuid4()), "tenant_id": str(uuid4())}
    
    # Não deve lançar exceção
    await handle_resource_deleted(payload)


@pytest.mark.anyio
async def test_handle_resource_deleted_missing_resource_id():
    """Verificar que resource.deleted lida com payload sem resource_id."""
    payload = {"tenant_id": str(uuid4())}
    
    # Não deve lançar exceção, apenas log warning
    await handle_resource_deleted(payload)
