import os
import sys
from pathlib import Path
from uuid import UUID as UUIDType

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

from app.main import app  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
from app.core.auth_dependencies import get_current_token  # noqa: E402


@pytest.fixture(autouse=True)
def prepare_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class DummyToken:
    def __init__(self, tenant_id=None):
        self.sub = UUIDType("00000000-0000-0000-0000-000000000000")
        # Use whatever tenant_id is provided, or a default
        if tenant_id:
            self.tenant_id = UUIDType(tenant_id) if isinstance(tenant_id, str) else tenant_id
        else:
            self.tenant_id = UUIDType("11111111-1111-1111-1111-111111111111")
        self.user_type = "admin"


# Global variable to store the current tenant_id for the test
# WARNING: This global state is not thread-safe. If tests ever run in parallel,
# this could lead to race conditions where one test's tenant_id affects another test.
# The fixture on line 73 resets this value after each test to minimize side effects.
# Ensure tests remain sequential or refactor to use thread-local storage if parallel execution is needed.
_test_tenant_id = None


def override_get_current_token():
    return DummyToken(tenant_id=_test_tenant_id)


def set_test_tenant_id(tenant_id):
    """Helper to set the tenant_id for the DummyToken in tests
    
    WARNING: This modifies global state and is not thread-safe.
    """
    global _test_tenant_id
    _test_tenant_id = str(tenant_id) if tenant_id else None


@pytest.fixture
def client():
    # sobrescreve autenticação somente durante os testes
    app.dependency_overrides[get_current_token] = override_get_current_token

    with TestClient(app) as test_client:
        yield test_client

    # limpa overrides depois
    app.dependency_overrides.clear()
    set_test_tenant_id(None)  # Reset tenant_id after each test
