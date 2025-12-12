from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import status

from shared import OrganizationSettings
from conftest import make_auth_headers


def _category_payload(tenant_id: str):
    return {
        "tenant_id": tenant_id,
        "name": "Salas",
        "description": "Salas de reunião",
        "type": "fisico",  # 👈 corrigido para atender ao schema
        "icon": "meeting_room",
        "color": "#FFAA00",
        "category_metadata": {
            "requires_qualification": False,
            "allows_multiple_bookings": False,
        },
    }


def _resource_payload(tenant_id: str, category_id: str):
    return {
        "tenant_id": tenant_id,
        "category_id": category_id,
        "name": "Sala 101",
        "description": "Sala com projetor",
        "status": "disponivel",
        "capacity": 10,
        "location": "Andar 1",
        "attributes": {"has_projector": True},
        "availability_schedule": {
            "timezone": "UTC",
            "schedule": [
                {"day_of_week": 0, "start_time": "09:00", "end_time": "18:00"}  # Monday
            ]
        },
    }


def test_resource_flow(client):
    tenant_id = str(uuid4())
    user_id = str(uuid4())
    headers = make_auth_headers(tenant_id, user_id, "admin")

    category_resp = client.post("/categories/", json=_category_payload(tenant_id), headers=headers)
    assert category_resp.status_code == status.HTTP_201_CREATED
    category_id = category_resp.json()["id"]

    resource_resp = client.post("/resources/", json=_resource_payload(tenant_id, category_id), headers=headers)
    assert resource_resp.status_code == status.HTTP_201_CREATED
    resource_id = resource_resp.json()["id"]

    list_resp = client.get("/resources/", params={"tenant_id": tenant_id}, headers=headers)
    assert list_resp.status_code == status.HTTP_200_OK
    resources = list_resp.json()
    assert len(resources) == 1
    assert resources[0]["category"]["id"] == category_id

    update_resp = client.put(f"/resources/{resource_id}", json={"status": "manutencao"}, headers=headers)
    assert update_resp.status_code == status.HTTP_200_OK
    assert update_resp.json()["status"] == "manutencao"

    delete_resp = client.delete(f"/resources/{resource_id}", headers=headers)
    assert delete_resp.status_code == status.HTTP_204_NO_CONTENT

    not_found = client.get(f"/resources/{resource_id}", headers=headers)
    assert not_found.status_code == status.HTTP_404_NOT_FOUND
def test_category_archival(client):
    tenant_id = str(uuid4())
    user_id = str(uuid4())
    headers = make_auth_headers(tenant_id, user_id, "admin")
    
    category = client.post("/categories/", json=_category_payload(tenant_id), headers=headers).json()
    category_id = category["id"]

    delete_resp = client.delete(f"/categories/{category_id}", headers=headers)
    assert delete_resp.status_code == status.HTTP_204_NO_CONTENT

    get_resp = client.get(f"/categories/{category_id}", headers=headers)
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


def test_availability_respects_settings(client):
    tenant_id = str(uuid4())
    user_id = str(uuid4())
    headers = make_auth_headers(tenant_id, user_id, "admin")

    client.app.state.settings_provider = lambda _tenant, auth_token=None: OrganizationSettings(
        timezone="UTC",
        working_hours_start=datetime.strptime("08:00", "%H:%M").time(),
        working_hours_end=datetime.strptime("18:00", "%H:%M").time(),
        booking_interval=60,
        advance_booking_days=10,
        cancellation_hours=24,
    )

    category_id = client.post("/categories/", json=_category_payload(tenant_id), headers=headers).json()["id"]
    resource_id = client.post("/resources/", json=_resource_payload(tenant_id, category_id), headers=headers).json()["id"]

    target_date = datetime.now(timezone.utc).date() + timedelta(days=1)
    while target_date.weekday() != 0:  # Monday
        target_date += timedelta(days=1)

    resp = client.get(f"/resources/{resource_id}/availability", params={"data": target_date.isoformat()}, headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["resource_id"] == resource_id
    assert body["tenant_id"] == tenant_id

    slots = body["slots"]
    assert slots, "Deve retornar pelo menos um horário disponível"

    parsed_slots = [datetime.fromisoformat(slot["start_time"]) for slot in slots]
    assert all(item.tzinfo is not None for item in parsed_slots)

    assert slots[0]["start_time"].startswith(f"{target_date}T09:00")
    assert slots[-1]["end_time"].startswith(f"{target_date}T18:00")


def test_availability_requires_future_date(client):
    tenant_id = str(uuid4())
    user_id = str(uuid4())
    headers = make_auth_headers(tenant_id, user_id, "admin")
    
    category_id = client.post("/categories/", json=_category_payload(tenant_id), headers=headers).json()["id"]
    resource_id = client.post("/resources/", json=_resource_payload(tenant_id, category_id), headers=headers).json()["id"]

    past_date = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    resp = client.get(f"/resources/{resource_id}/availability", params={"data": past_date}, headers=headers)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "Data deve ser igual ou posterior a hoje" in resp.json()["detail"]


def test_openapi_version(client):
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["openapi"] == "3.0.3"
