import os
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from sqlalchemy.exc import OperationalError
from app.core.database import Base, engine
from app.models import booking as booking_models
from app.routers import bookings
from shared import EventPublisher, load_service_config
import time

tags_metadata = [
    {
        "name": "Bookings",
        "description": "Gerenciamento de agendamentos, conflitos e cancelamentos.",
    }
]

_CONFIG = load_service_config("reservation")
_ROOT_PATH = os.getenv("APP_ROOT_PATH", "")
_EVENT_PUBLISHER = EventPublisher(_CONFIG.redis.url, _CONFIG.redis.stream)

app = FastAPI(
    title="Reservation Service",
    version="0.1.0",
    description="API responsável pelas reservas, conflitos e eventos emitidos.",
    openapi_tags=tags_metadata,
    root_path=_ROOT_PATH,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.config = _CONFIG
app.state.event_publisher = _EVENT_PUBLISHER


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


app.openapi = custom_openapi_schema


@app.on_event("startup")
def on_startup():
    for tentativa in range(10):
        try:
            _ = (booking_models.Booking, booking_models.BookingEvent)
            Base.metadata.create_all(bind=engine)
            break
        except OperationalError as exc:  # pragma: no cover
            wait_seconds = 2
            print(
                f"[Reservation Service] Banco indisponível, aguardando {wait_seconds}s... tentativa {tentativa + 1}",
                exc,
            )
            time.sleep(wait_seconds)


app.include_router(bookings.router)


@app.get("/")
def root():
    return {
        "service": "reservation",
        "status": "ok",
        "docs_url": "/docs",
        "config": {
            "redis_stream": _CONFIG.redis.stream,
        },
    }
