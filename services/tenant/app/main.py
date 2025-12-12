# app/main.py
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from html import escape

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse

from app.core.database import Base, engine
from app.models import tenant as tenant_models
from app.routers import endpoints as tenants, webhooks
from shared import (
    database_lifespan_factory,
    load_service_config,
    EventPublisher,
    EventConsumer,
    cleanup_consumer,
    create_health_router,
    configure_cors,
)
from app.consumers.booking_consumer import (
    handle_booking_created,
    handle_booking_cancelled,
    handle_booking_updated,
)

# Configure logging
if not logging.root.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

tags_metadata = [
    {
        "name": "Tenants",
        "description": "Gerenciamento de organizações white label e respectivas configurações de agenda.",
    }
]

_CONFIG = load_service_config("tenant")
_ROOT_PATH = os.getenv("APP_ROOT_PATH") or ""

# Event Publisher for tenant.deleted events (only if Redis is configured)
_EVENT_PUBLISHER = (
    EventPublisher(_CONFIG.redis.url, "deletion-events")
    if isinstance(_CONFIG.redis.url, str) and _CONFIG.redis.url.strip()
    else None
)

IS_TEST = os.getenv("PYTEST_CURRENT_TEST") is not None

# Consumer instances
_booking_consumer: EventConsumer | None = None
_booking_consumer_task: asyncio.Task | None = None


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Combined lifespan with database and event consumers."""
    global _booking_consumer, _booking_consumer_task
    
    # Database startup with retries
    logger.info("Starting Tenant Service...")
    for attempt in range(10):
        try:
            await asyncio.to_thread(Base.metadata.create_all, bind=engine)
            break
        except Exception as e:
            if attempt < 9:
                logger.warning(f"Database unavailable, retrying... attempt {attempt + 1}: {e}")
                await asyncio.sleep(2.0)
            else:
                logger.error("Database unavailable after 10 attempts, giving up.")
                raise
    
    # Start event consumer for booking events (webhooks)
    if _CONFIG.redis.url:
        _booking_consumer = EventConsumer(
            redis_url=_CONFIG.redis.url,
            stream_name="booking-events",
            group_name="tenant-service",
            consumer_name="tenant-webhook-worker-1",
        )
        _booking_consumer.register_handler("booking.created", handle_booking_created)
        _booking_consumer.register_handler("booking.cancelled", handle_booking_cancelled)
        _booking_consumer.register_handler("booking.updated", handle_booking_updated)
        _booking_consumer_task = asyncio.create_task(_booking_consumer.start())
        logger.info("Booking event consumer (webhooks) started")
    
    yield
    
    # Cleanup consumer
    await cleanup_consumer(_booking_consumer, _booking_consumer_task, logger)
    logger.info("Tenant Service stopped")

lifespan = app_lifespan

app = FastAPI(
    title="Tenant Service",
    version="0.1.0",
    description="API responsável pela administração de tenants.",
    openapi_tags=tags_metadata,
    root_path=_ROOT_PATH,
    lifespan=lifespan,
    docs_url=None,
    redoc_url="/redoc",
)

app.state.config = _CONFIG
app.state.event_publisher = _EVENT_PUBLISHER

# Initialize Redis cache if available
from shared.cache import create_redis_cache
cache = create_redis_cache(_CONFIG.redis.url)
if cache:
    app.state.redis_cache = cache

# Configure CORS
configure_cors(app)


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

# Custom Swagger UI with correct openapi.json path
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link type="text/css" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
        <title>{escape(app.title)} - Swagger UI</title>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
        const ui = SwaggerUIBundle({{
            url: window.location.pathname.replace(/\/docs$/, '') + '/openapi.json',
            dom_id: '#swagger-ui',
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout",
            deepLinking: true
        }})
        </script>
    </body>
    </html>
    """)

# Health check endpoints
health_router = create_health_router(
    service_name="tenant",
    database_engine=engine,
    redis_client=_CONFIG.redis.url if _CONFIG.redis.url else None,
)
app.include_router(health_router)

# add as rotas definidas em endpoints.py aqui, pq aí as urls funcionam
app.include_router(tenants.router, prefix="/tenants")
app.include_router(webhooks.router)

@app.get("/")
def root():
    return {
        "service": "tenant",
        "status": "ok",
        "docs_url": "/docs",
        "config": {
            "redis_stream": _CONFIG.redis.stream,
        },
    }
