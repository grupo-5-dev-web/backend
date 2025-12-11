from uuid import uuid4

from fastapi import status
from conftest import make_auth_headers


def _user_payload():
    tenant_id = str(uuid4())
    return {
        "tenant_id": tenant_id,
        "name": "Alice",
        "email": "alice@example.com",
        "user_type": "admin",
        "phone": "+5511999999999",
        "department": "Operations",
        "is_active": True,
        "permissions": {
            "can_book": True,
            "can_manage_resources": True,
            "can_manage_users": True,
            "can_view_all_bookings": True,
        },
        "metadata": {"timezone": "America/Sao_Paulo"},
        "password": "secretpass",
    }


def test_create_list_update_delete_user(client):
    payload = _user_payload()

    response = client.post("/users/", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    user_data = response.json()
    user_id = user_data["id"]
    
    # Gerar headers de autenticação como admin do tenant criado
    headers = make_auth_headers(payload["tenant_id"], user_id, "admin")

    list_response = client.get("/users/", params={"tenant_id": payload["tenant_id"]}, headers=headers)
    assert list_response.status_code == status.HTTP_200_OK
    users = list_response.json()
    assert len(users) == 1
    assert users[0]["email"] == payload["email"]

    update_response = client.put(
        f"/users/{user_id}",
        json={"name": "Alice Updated", "metadata": {"timezone": "UTC"}},
        headers=headers,
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["name"] == "Alice Updated"
    assert update_response.json()["metadata"]["timezone"] == "UTC"

    delete_response = client.delete(f"/users/{user_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # ✔ delete real → criar outro usuário admin para verificar o 404
    # (não podemos usar o token do usuário deletado)
    other_payload = _user_payload()
    other_payload["tenant_id"] = payload["tenant_id"]  # Mesmo tenant!
    other_payload["email"] = "other@example.com"
    other_response = client.post("/users/", json=other_payload)
    other_id = other_response.json()["id"]
    other_headers = make_auth_headers(payload["tenant_id"], other_id, "admin")
    
    get_response = client.get(f"/users/{user_id}", headers=other_headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


def test_duplicate_email_returns_400(client):
    payload = _user_payload()

    first = client.post("/users/", json=payload)
    assert first.status_code == status.HTTP_201_CREATED

    second = client.post("/users/", json=payload)
    assert second.status_code == status.HTTP_400_BAD_REQUEST
    assert second.json()["detail"] == "Já existe um usuário cadastrado com este e-mail."


def test_openapi_version(client):
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["openapi"] == "3.0.3"
