import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

SECRET_KEY = os.getenv("SECRET_KEY", "ci-test-secret")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS512")


def make_auth_headers(tenant_id: str, user_id: str, user_type: str = "admin") -> dict:
    """
    Gera um JWT compatível com o TokenPayload do serviço de user,
    para ser usado nos headers dos testes.
    """
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "user_type": user_type,
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"Authorization": f"Bearer {token}"}

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

# Garante que o app e os testes usem o mesmo segredo/algoritmo
os.environ.setdefault("SECRET_KEY", SECRET_KEY)
os.environ.setdefault("JWT_ALGORITHM", ALGORITHM)

os.environ.setdefault("USER_DATABASE_URL", f"sqlite:///{SERVICE_DIR / 'test_user.db'}")
os.environ["REDIS_URL"] = ""  # Disable event consumer in tests

from app.main import app  # noqa: E402
from app.core.database import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def prepare_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
