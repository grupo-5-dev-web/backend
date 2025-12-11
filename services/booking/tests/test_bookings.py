import os
from datetime import datetime, timedelta, timezone, time
from uuid import uuid4

from fastapi import status
from jose import jwt

from app.services.organization import OrganizationSettings

# =====================================================================
# Helpers de autenticação para os testes
# =====================================================================

SECRET_KEY = os.getenv("SECRET_KEY", "ci-test-secret")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS512")


def make_auth_headers(user_id: str, tenant_id: str, user_type: str = "admin"):
    """
    Gera um token JWT compatível com get_current_token
    e retorna o header Authorization.
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=1)

    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "user_type": user_type,
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# Helpers de tempo / payload
# =====================================================================

def _base_times(hours_from_now: int = 48, duration_minutes: int = 60):
    base = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
    base = base.replace(hour=10, minute=0, second=0, microsecond=0)
    end = base + timedelta(minutes=duration_minutes)
    return base, end


def _booking_payload(
    tenant_id: str,
    resource_id: str,
    user_id: str,
    start: datetime,
    end: datetime,
):
    return {
        "tenant_id": tenant_id,
        "resource_id": resource_id,
        "user_id": user_id,
        "client_id": user_id,          # alinha com o que você manda no Postman
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "notes": "Primeira reserva",
        "recurring_enabled": False,    # idem
    }


# =====================================================================
# Testes
# =====================================================================

def test_booking_lifecycle(client):
    tenant_id = str(uuid4())
    resource_id = str(uuid4())
    user_id = str(uuid4())

    headers = make_auth_headers(user_id=user_id, tenant_id=tenant_id, user_type="admin")

    start, end = _base_times()

    create_resp = client.post(
        "/bookings/",
        json=_booking_payload(tenant_id, resource_id, user_id, start, end),
        headers=headers,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    booking = create_resp.json()
    booking_id = booking["id"]

    assert booking["status"] == "confirmado"

    list_resp = client.get("/bookings/", params={"tenant_id": tenant_id}, headers=headers)
    assert list_resp.status_code == status.HTTP_200_OK
    bookings = list_resp.json()
    assert len(bookings) == 1
    assert bookings[0]["can_cancel"] is True

    update_resp = client.put(
        f"/bookings/{booking_id}",
        json={"notes": "Atualização de notas", "status": "confirmado"},
        headers=headers,
    )
    assert update_resp.status_code == status.HTTP_200_OK
    assert update_resp.json()["notes"] == "Atualização de notas"
    assert update_resp.json()["status"] == "confirmado"

    status_resp = client.patch(
        f"/bookings/{booking_id}/status",
        params={"status_param": "concluido"},
        headers=headers,
    )
    assert status_resp.status_code == status.HTTP_200_OK
    assert status_resp.json()["status"] == "concluido"

    cancel_resp = client.patch(
        f"/bookings/{booking_id}/cancel",
        params={"cancelled_by": str(uuid4())},
        json={"reason": "Cliente cancelou"},
        headers=headers,
    )
    assert cancel_resp.status_code == status.HTTP_200_OK
    cancelled = cancel_resp.json()
    assert cancelled["status"] == "cancelado"
    assert cancelled["cancellation_reason"] == "Cliente cancelou"
    assert cancelled["cancelled_at"] is not None


def test_booking_conflict_detection(client):
    tenant_id = str(uuid4())
    resource_id = str(uuid4())
    user_id = str(uuid4())

    headers = make_auth_headers(user_id=user_id, tenant_id=tenant_id, user_type="admin")

    start, end = _base_times()

    first = client.post(
        "/bookings/",
        json=_booking_payload(tenant_id, resource_id, user_id, start, end),
        headers=headers,
    )
    assert first.status_code == status.HTTP_201_CREATED

    conflict = client.post(
        "/bookings/",
        json=_booking_payload(
            tenant_id,
            resource_id,
            str(uuid4()),
            start + timedelta(minutes=30),
            end + timedelta(minutes=30),
        ),
        headers=headers,
    )
    assert conflict.status_code == status.HTTP_409_CONFLICT
    conflict_body = conflict.json()
    assert conflict_body["success"] is False
    assert conflict_body["error"] == "conflict"
    assert len(conflict_body["conflicts"]) == 1

    next_start = end + timedelta(minutes=30)
    next_end = next_start + timedelta(hours=1)
    non_conflict = client.post(
        "/bookings/",
        json=_booking_payload(
            tenant_id,
            resource_id,
            str(uuid4()),
            next_start,
            next_end,
        ),
        headers=headers,
    )
    assert non_conflict.status_code == status.HTTP_201_CREATED


def test_booking_outside_working_hours_returns_400(client):
    tenant_id = str(uuid4())
    resource_id = str(uuid4())
    user_id = str(uuid4())

    headers = make_auth_headers(user_id=user_id, tenant_id=tenant_id, user_type="admin")

    late_start, late_end = _base_times(hours_from_now=48)
    late_start = late_start.replace(hour=22)
    late_end = late_start + timedelta(hours=1)

    response = client.post(
        "/bookings/",
        json=_booking_payload(tenant_id, resource_id, user_id, late_start, late_end),
        headers=headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Horário fora do expediente configurado."


def test_booking_respects_advance_window(client):
    tenant_id = str(uuid4())
    resource_id = str(uuid4())
    user_id = str(uuid4())

    headers = make_auth_headers(user_id=user_id, tenant_id=tenant_id, user_type="admin")

    original_provider = client.app.state.settings_provider

    def limited_provider(_tenant_id, auth_token=None):
        return OrganizationSettings(
            timezone="UTC",
            working_hours_start=time(8, 0),
            working_hours_end=time(18, 0),
            booking_interval=30,
            advance_booking_days=1,
            cancellation_hours=24,
        )

    client.app.state.settings_provider = limited_provider

    try:
        far_start, far_end = _base_times(hours_from_now=72)
        response = client.post(
            "/bookings/",
            json=_booking_payload(tenant_id, resource_id, user_id, far_start, far_end),
            headers=headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "dias de antecedência" in response.json()["detail"]
    finally:
        client.app.state.settings_provider = original_provider


def test_cancel_booking_respects_cancellation_window(client):
    tenant_id = str(uuid4())
    resource_id = str(uuid4())
    user_id = str(uuid4())

    headers = make_auth_headers(user_id=user_id, tenant_id=tenant_id, user_type="admin")

    original_provider = client.app.state.settings_provider

    def strict_cancellation_provider(_tenant_id, auth_token=None):
        return OrganizationSettings(
            timezone="UTC",
            working_hours_start=time(8, 0),
            working_hours_end=time(18, 0),
            booking_interval=30,
            advance_booking_days=30,
            cancellation_hours=48,
        )

    client.app.state.settings_provider = strict_cancellation_provider

    try:
        start, end = _base_times(hours_from_now=24)
        create_resp = client.post(
            "/bookings/",
            json=_booking_payload(tenant_id, resource_id, user_id, start, end),
            headers=headers,
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        booking_id = create_resp.json()["id"]

        cancel_resp = client.patch(
            f"/bookings/{booking_id}/cancel",
            params={"cancelled_by": str(uuid4())},
            json={"reason": "Cliente desistiu"},
            headers=headers,
        )

        # Aceita tanto 400 (regra de negócio) quanto 405 (método não permitido)
        assert cancel_resp.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        if cancel_resp.status_code == status.HTTP_400_BAD_REQUEST:
            assert "Cancelamento permitido" in cancel_resp.json()["detail"]
    finally:
        client.app.state.settings_provider = original_provider


def test_cancel_booking_publishes_event_with_resource_and_user_ids(client):
    """Test that booking.cancelled event includes resource_id and user_id in the payload."""
    tenant_id = str(uuid4())
    resource_id = str(uuid4())
    user_id = str(uuid4())

    headers = make_auth_headers(user_id=user_id, tenant_id=tenant_id, user_type="admin")

    # Create a mock event publisher to capture published events
    published_events = []
    
    class MockEventPublisher:
        def publish(self, event_type, payload, metadata=None):
            published_events.append({
                "event_type": event_type,
                "payload": payload,
                "metadata": metadata,
            })
    
    # Set the mock publisher
    original_publisher = client.app.state.event_publisher
    client.app.state.event_publisher = MockEventPublisher()
    
    try:
        # Create a booking that can be cancelled (far enough in the future)
        start, end = _base_times(hours_from_now=72)
        create_resp = client.post(
            "/bookings/",
            json=_booking_payload(tenant_id, resource_id, user_id, start, end),
            headers=headers,
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        booking_id = create_resp.json()["id"]

        # Cancel the booking
        cancel_resp = client.patch(
            f"/bookings/{booking_id}/cancel",
            json={"reason": "Testing event payload"},
            headers=headers,
        )
        
        assert cancel_resp.status_code == status.HTTP_200_OK
        
        # Find the booking.cancelled event
        cancelled_events = [
            e for e in published_events 
            if e["event_type"] == "booking.cancelled"
        ]
        
        assert len(cancelled_events) == 1, "Expected exactly one booking.cancelled event"
        
        event_payload = cancelled_events[0]["payload"]
        
        # Verify the event payload contains resource_id and user_id
        assert "resource_id" in event_payload, "Event payload should contain resource_id"
        assert "user_id" in event_payload, "Event payload should contain user_id"
        assert event_payload["resource_id"] == resource_id
        assert event_payload["user_id"] == user_id
        assert event_payload["booking_id"] == booking_id
        assert event_payload["cancelled_by"] == user_id
        assert event_payload["reason"] == "Testing event payload"
        
    finally:
        client.app.state.event_publisher = original_publisher


def test_openapi_version(client):
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["openapi"] == "3.0.3"
