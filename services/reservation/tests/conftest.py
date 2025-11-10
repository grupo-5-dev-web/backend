import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from datetime import time

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

os.environ.setdefault("RESERVATION_DATABASE_URL", f"sqlite:///{SERVICE_DIR / 'test_reservation.db'}")
os.environ.setdefault("EVENT_STREAM", "test-stream")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.main import app  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
from app.services.organization import OrganizationSettings  # noqa: E402


@pytest.fixture(autouse=True)
def prepare_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    app.state.event_publisher = None
    default_settings = OrganizationSettings(
        timezone="UTC",
        working_hours_start=time(8, 0),
        working_hours_end=time(18, 0),
        booking_interval=30,
        advance_booking_days=30,
        cancellation_hours=24,
    )

    app.state.settings_provider = lambda _tenant_id: default_settings
    with TestClient(app) as test_client:
        yield test_client

