import os
from contextlib import asynccontextmanager
from html import escape

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
from app.routers import bookings
from app.services.organization import default_settings_provider
from app.consumers import handle_resource_deleted, handle_user_deleted, handle_tenant_deleted
from shared import EventPublisher, EventConsumer, cleanup_consumer, load_service_config
import asyncio
import logging

# Configure logging
if not logging.root.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

tags_metadata = [
    {
        "name": "Bookings",
        "description": "Gerenciamento de agendamentos, conflitos e cancelamentos.",
    }
]

_CONFIG = load_service_config("booking")
_ROOT_PATH = os.getenv("APP_ROOT_PATH", "")
_EVENT_PUBLISHER = EventPublisher(_CONFIG.redis.url, _CONFIG.redis.stream) if _CONFIG.redis.url else None

# Consumer instance
_consumer: EventConsumer | None = None
_consumer_task: asyncio.Task | None = None


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Combined lifespan with database and event consumer."""
    global _consumer, _consumer_task
    
    # Database startup with retries
    logger.info("Starting Booking Service...")
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
    
    # Start event consumer for deletion events
    if _CONFIG.redis.url:
        _consumer = EventConsumer(
            redis_url=_CONFIG.redis.url,
            stream_name="deletion-events",
            group_name="booking-service",
            consumer_name="booking-worker-1",
        )
        
        # Register event handlers for cascading deletes
        _consumer.register_handler("resource.deleted", handle_resource_deleted)
        _consumer.register_handler("user.deleted", handle_user_deleted)
        _consumer.register_handler("tenant.deleted", handle_tenant_deleted)
        
        # Start consumer in background
        _consumer_task = asyncio.create_task(_consumer.start())
        logger.info("Deletion event consumer started")
    
    yield
    
    # Cleanup using shared helper
    await cleanup_consumer(_consumer, _consumer_task, logger)
    logger.info("Booking Service stopped")

lifespan = app_lifespan

app = FastAPI(
    title="Booking Service",
    version="0.1.0",
    description="API responsável pelas reservas, conflitos e eventos emitidos.",
    openapi_tags=tags_metadata,
    root_path=_ROOT_PATH,
    lifespan=lifespan,
    docs_url=None,
    redoc_url="/redoc",
)

# CORS configuration with smart defaults
raw_origins = os.getenv("CORS_ORIGINS", "")

if raw_origins:
    # Explicit configuration provided
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
else:
    # Fallback: allow all for dev/test, warn in production
    is_dev = os.getenv("ENVIRONMENT", "development") in ["development", "dev", "test"]
    if is_dev:
        origins = ["*"]
        logger.warning("CORS_ORIGINS not set. Using wildcard (*) for development. Set CORS_ORIGINS in production!")
    else:
        logger.error("CORS_ORIGINS not configured! Set CORS_ORIGINS environment variable.")
        origins = ["*"]  # Fallback to avoid breaking, but logged as error

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
