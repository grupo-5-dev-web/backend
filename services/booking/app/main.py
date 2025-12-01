import os

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.database import Base, engine
from app.models import booking as booking_models
from app.routers import bookings
from app.services.organization import default_settings_provider
from shared import EventPublisher, database_lifespan_factory, load_service_config

tags_metadata = [
    {
        "name": "Bookings",
        "description": "Gerenciamento de agendamentos, conflitos e cancelamentos.",
    }
]

_CONFIG = load_service_config("booking")
_ROOT_PATH = os.getenv("APP_ROOT_PATH", "")
_EVENT_PUBLISHER = EventPublisher(_CONFIG.redis.url, _CONFIG.redis.stream)

lifespan = database_lifespan_factory(
    service_name="Booking Service",
    metadata=Base.metadata,
    engine=engine,
    models=(booking_models.Booking, booking_models.BookingEvent),
)

app = FastAPI(
    title="Booking Service",
    version="0.1.0",
    description="API responsável pelas reservas, conflitos e eventos emitidos.",
    openapi_tags=tags_metadata,
    root_path=_ROOT_PATH,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.config = _CONFIG
app.state.event_publisher = _EVENT_PUBLISHER
app.state.settings_provider = default_settings_provider


def custom_openapi_schema():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["openapi"] = "3.0.3"
    app.openapi_schema = schema
    return app.openapi_schema


def is_testing():
    return os.getenv("PYTEST_CURRENT_TEST") is not None


app.openapi = custom_openapi_schema
app.state.tenant_service_url = os.getenv("TENANT_SERVICE_URL")
app.state.resource_service_url = os.getenv("RESOURCE_SERVICE_URL")
app.state.user_service_url = os.getenv("USER_SERVICE_URL")
app.include_router(bookings.router)


@app.get("/")
def root():
    return {
        "service": "booking",
        "status": "ok",
        "docs_url": "/docs",
        "config": {
            "redis_stream": _CONFIG.redis.stream,
        },
    }
