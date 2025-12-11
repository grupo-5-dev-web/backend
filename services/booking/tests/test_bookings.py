from datetime import datetime, timedelta, timezone
from datetime import time
from uuid import uuid4
import os
from fastapi import status
from .conftest import make_auth_headers
from app.services.organization import OrganizationSettings

SECRET_KEY = os.getenv("SECRET_KEY", "ci-test-secret")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS512")

def _base_times(hours_from_now: int = 48, duration_minutes: int = 60):
    base = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
    base = base.replace(hour=10, minute=0, second=0, microsecond=0)
    end = base + timedelta(minutes=duration_minutes)
    return base, end


def _booking_payload(tenant_id: str, resource_id: str, user_id: str, start: datetime, end: datetime):
    return {
        "tenant_id": tenant_id,
        "resource_id": resource_id,
        "user_id": user_id,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "notes": "Primeira reserva",
    }


def test_booking_lifecycle(client):
    tenant_id = str(uuid4())
    resource_id = str(uuid4())
    user_id = str(uuid4())

    start, end = _base_times()

    # CREATE
    create_resp = client.post(
        "/bookings/",
        json=_booking_payload(tenant_id, resource_id, user_id, start, end),
        headers=make_auth_headers(tenant_id, user_id, "user"),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    booking = create_resp.json()
    booking_id = booking["id"]
    assert booking["status"] == "pendente"

    # LIST
    list_resp = client.get(
        "/bookings/",
        params={"tenant_id": tenant_id},
        headers=make_auth_headers(tenant_id, user_id, "user"),
    )
    assert list_resp.status_code == status.HTTP_200_OK
    bookings = list_resp.json()
    assert len(bookings) == 1
    assert bookings[0]["can_cancel"] is True

    # UPDATE
    update_resp = client.put(
        f"/bookings/{booking_id}",
        json={"notes": "Atualização de notas", "status": "confirmado"},
        headers=make_auth_headers(tenant_id, user_id, "user"),
    )
    assert update_resp.status_code == status.HTTP_200_OK
    assert update_resp.json()["notes"] == "Atualização de notas"
    assert update_resp.json()["status"] == "confirmado"

    # CHANGE STATUS
    status_resp = client.patch(
        f"/bookings/{booking_id}/status",
        params={"status_param": "concluido"},
        headers=make_auth_headers(tenant_id, user_id, "user"),
    )
    assert status_resp.status_code == status.HTTP_200_OK
    assert status_resp.json()["status"] == "concluido"

    # CANCEL
    cancel_resp = client.patch(
        f"/bookings/{booking_id}/cancel",
        params={"cancelled_by": str(uuid4())},
        json={"reason": "Cliente cancelou"},
        headers=make_auth_headers(tenant_id, user_id, "user"),
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

    start, end = _base_times()

    # 1ª reserva
    first = client.post(
        "/bookings/",
        json=_booking_payload(tenant_id, resource_id, user_id, start, end),
        headers=make_auth_headers(tenant_id, user_id, "user"),
    )
    assert first.status_code == status.HTTP_201_CREATED

    # 2ª reserva em conflito, com outro usuário
    conflict_user_id = str(uuid4())
    conflict = client.post(
        "/bookings/",
        json=_booking_payload(
            tenant_id,
            resource_id,
            conflict_user_id,
            start + timedelta(minutes=30),
            end + timedelta(minutes=30),
        ),
        headers=make_auth_headers(tenant_id, conflict_user_id, "user"),
    )
    assert conflict.status_code == status.HTTP_409_CONFLICT
    conflict_body = conflict.json()
    assert conflict_body["success"] is False
    assert conflict_body["error"] == "conflict"
    assert len(conflict_body["conflicts"]) == 1

    # 3ª reserva fora do intervalo de conflito, com outro usuário ainda
    next_user_id = str(uuid4())
    next_start = end + timedelta(minutes=30)
    next_end = next_start + timedelta(hours=1)
    non_conflict = client.post(
        "/bookings/",
        json=_booking_payload(
            tenant_id,
            resource_id,
            next_user_id,
            next_start,
            next_end,
        ),
        headers=make_auth_headers(tenant_id, next_user_id, "user"),
    )
    assert non_conflict.status_code == status.HTTP_201_CREATED


def test_booking_outside_working_hours_returns_400(client):
    tenant_id = str(uuid4())
    resource_id = str(uuid4())
    user_id = str(uuid4())

    late_start, late_end = _base_times(hours_from_now=48)
    late_start = late_start.replace(hour=22)
    late_end = late_start + timedelta(hours=1)

    response = client.post(
        "/bookings/",
        json=_booking_payload(tenant_id, resource_id, user_id, late_start, late_end),
        headers=make_auth_headers(tenant_id, user_id, "user"),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Horário fora do expediente configurado."


def test_booking_respects_advance_window(client):
    tenant_id = str(uuid4())
    resource_id = str(uuid4())
    user_id = str(uuid4())

    original_provider = client.app.state.settings_provider

    def limited_provider(_tenant_id):
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
            headers=make_auth_headers(tenant_id, user_id, "user"),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "dias de antecedência" in response.json()["detail"]
    finally:
        client.app.state.settings_provider = original_provider


def test_cancel_booking_respects_cancellation_window(client):
    tenant_id = str(uuid4())
    resource_id = str(uuid4())
    user_id = str(uuid4())

    original_provider = client.app.state.settings_provider

    def strict_cancellation_provider(_tenant_id):
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
            headers=make_auth_headers(tenant_id, user_id, "user"),
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        booking_id = create_resp.json()["id"]

        cancel_resp = client.patch(
            f"/bookings/{booking_id}/cancel",
            params={"cancelled_by": str(uuid4())},
            json={"reason": "Cliente desistiu"},
            headers=make_auth_headers(tenant_id, user_id, "user"),
        )
        assert cancel_resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cancelamento permitido" in cancel_resp.json()["detail"]
    finally:
        client.app.state.settings_provider = original_provider


def test_openapi_version(client):
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["openapi"] == "3.0.3"
