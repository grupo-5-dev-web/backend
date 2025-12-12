from uuid import uuid4

from fastapi import status
from conftest import set_test_tenant_id


def _labels():
    return {
        "resource_singular": "Recurso",
        "resource_plural": "Recursos",
        "booking_label": "Agendamento",
        "user_label": "Usuário",
    }


def _settings():
    return {
        "business_type": "clinica",
        "timezone": "America/Sao_Paulo",
        "working_hours_start": "08:00:00",
        "working_hours_end": "18:00:00",
        "booking_interval": 30,
        "advance_booking_days": 15,
        "cancellation_hours": 12,
        "custom_labels": _labels(),
    }


def _tenant_payload(domain: str):
    return {
        "name": "Tenant Exemplo",
        "domain": domain,
        "logo_url": "https://example.com/logo.png",
        "theme_primary_color": "#123456",
        "plan": "basico",   # <-- ALTERADO
        "settings": _settings(),
    }


def test_tenant_crud_flow(client):
    payload = _tenant_payload("tenant-exemplo.com")

    create_resp = client.post("/tenants/", json=payload)
    assert create_resp.status_code == status.HTTP_200_OK
    tenant = create_resp.json()
    tenant_id = tenant["id"]
    assert tenant["settings"]["business_type"] == payload["settings"]["business_type"]
    
    # Set the token to match this tenant for authenticated operations
    set_test_tenant_id(tenant_id)

    list_resp = client.get("/tenants/")
    assert list_resp.status_code == status.HTTP_200_OK
    assert len(list_resp.json()) == 1

    get_resp = client.get(f"/tenants/{tenant_id}")
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["domain"] == payload["domain"]

    update_resp = client.put(
        f"/tenants/{tenant_id}",
        json={"name": "Tenant Atualizado", "plan": "corporativo"},  # <-- ALTERADO
    )
    assert update_resp.status_code == status.HTTP_200_OK
    assert update_resp.json()["name"] == "Tenant Atualizado"
    assert update_resp.json()["plan"] == "corporativo"

    delete_resp = client.delete(f"/tenants/{tenant_id}")
    assert delete_resp.status_code == status.HTTP_204_NO_CONTENT

    missing_resp = client.get(f"/tenants/{tenant_id}")
    assert missing_resp.status_code == status.HTTP_404_NOT_FOUND


def test_duplicate_domain_returns_400(client):
    domain = "duplicado.com"
    first = client.post("/tenants/", json=_tenant_payload(domain))
    assert first.status_code == status.HTTP_200_OK

    second = client.post("/tenants/", json=_tenant_payload(domain))
    assert second.status_code == status.HTTP_400_BAD_REQUEST
    assert second.json()["detail"] == "Domínio já cadastrado."


def test_settings_not_found_returns_404(client):
    tenant_id = str(uuid4())
    set_test_tenant_id(tenant_id)  # Set token to match this tenant
    response = client.get(f"/tenants/{tenant_id}/settings")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_openapi_version(client):
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["openapi"] == "3.0.3"
