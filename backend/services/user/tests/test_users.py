from uuid import UUID, uuid4

from fastapi import status
from app.core.database import SessionLocal
from app.models.user import User
from app.routers import crud


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

    list_response = client.get("/users/", params={"tenant_id": payload["tenant_id"]})
    assert list_response.status_code == status.HTTP_200_OK
    users = list_response.json()
    assert len(users) == 1
    assert users[0]["email"] == payload["email"]

    update_response = client.put(
        f"/users/{user_id}",
        json={"name": "Alice Updated", "metadata": {"timezone": "UTC"}},
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["name"] == "Alice Updated"
    assert update_response.json()["metadata"]["timezone"] == "UTC"

    delete_response = client.delete(f"/users/{user_id}")
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    get_response = client.get(f"/users/{user_id}")
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["is_active"] is False


def test_duplicate_email_returns_400(client):
    payload = _user_payload()

    first = client.post("/users/", json=payload)
    assert first.status_code == status.HTTP_201_CREATED

    second = client.post("/users/", json=payload)
    assert second.status_code == status.HTTP_400_BAD_REQUEST
    assert second.json()["detail"] == "E-mail já cadastrado para este tenant"


def test_openapi_version(client):
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["openapi"] == "3.0.3"


def test_password_is_hashed_on_create(client):
    payload = _user_payload()

    response = client.post("/users/", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    user_id = UUID(response.json()["id"])

    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user is not None
        assert user.password_hash is not None
        assert user.password_hash != payload["password"]
        assert crud.verify_password(payload["password"], user.password_hash)


def test_password_is_hashed_on_update(client):
    payload = _user_payload()
    create_response = client.post("/users/", json=payload)
    assert create_response.status_code == status.HTTP_201_CREATED
    user_id = UUID(create_response.json()["id"])

    with SessionLocal() as db:
        original_hash = db.get(User, user_id).password_hash

    new_password = "newsecretpass"
    update_response = client.put(f"/users/{user_id}", json={"password": new_password})
    assert update_response.status_code == status.HTTP_200_OK

    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.password_hash != original_hash
        assert crud.verify_password(new_password, user.password_hash)
        assert not crud.verify_password(payload["password"], user.password_hash)
