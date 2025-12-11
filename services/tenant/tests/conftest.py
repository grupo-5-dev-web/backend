import os
import sys
from pathlib import Path
from app.main import app  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
from app.core.auth_dependencies import get_current_token  # noqa: E402
import pytest
from fastapi.testclient import TestClient

SERVICE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = SERVICE_DIR.parent.parent

service_path = str(SERVICE_DIR)
shared_path = str(ROOT_DIR / "services")
for path in (service_path, shared_path):
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        sys.modules.pop(module_name)

os.environ.setdefault("TENANT_DATABASE_URL", f"sqlite:///{SERVICE_DIR / 'test_tenant.db'}")

@pytest.fixture(autouse=True)
def prepare_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class DummyToken:
    sub = "00000000-0000-0000-0000-000000000000"
    tenant_id = "11111111-1111-1111-1111-111111111111"
    user_type = "admin"


def override_get_current_token():
    return DummyToken()

@pytest.fixture
def client():
    # sobrescreve autenticação somente durante os testes
    app.dependency_overrides[get_current_token] = override_get_current_token

    with TestClient(app) as test_client:
        yield test_client

    # limpa overrides depois
    app.dependency_overrides.clear()
