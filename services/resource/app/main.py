import os
from contextlib import asynccontextmanager
from html import escape

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse

from app.core.database import Base, engine
from app.routers import categories, resources
from shared import default_settings_provider, load_service_config, EventConsumer, cleanup_consumer
from app.consumers import (
    handle_booking_created,
    handle_booking_cancelled,
    handle_booking_updated,
)
import asyncio
import logging

# Configure logging only if not already configured
if not logging.root.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

tags_metadata = [
    {
        "name": "Resource Categories",
        "description": "Gerencie grupos de recursos com metadados e campos customizados.",
    },
    {
        "name": "Resources",
        "description": "CRUD de recursos físicos, humanos ou digitais vinculados a tenants.",
    },
]

_CONFIG = load_service_config("resource")
_ROOT_PATH = os.getenv("APP_ROOT_PATH", "")

# Consumer instance
_consumer: EventConsumer | None = None
_consumer_task: asyncio.Task | None = None


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Combined lifespan with database and event consumer."""
    global _consumer, _consumer_task
    
    # Database startup with retries
    logger.info("Starting Resource Service...")
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
    
    # Start event consumer
    if _CONFIG.redis.url:
        _consumer = EventConsumer(
            redis_url=_CONFIG.redis.url,
            stream_name="booking-events",
            group_name="resource-service",
            consumer_name="resource-worker-1",
        )
        
        # Register event handlers
        _consumer.register_handler("booking.created", handle_booking_created)
        _consumer.register_handler("booking.cancelled", handle_booking_cancelled)
        _consumer.register_handler("booking.updated", handle_booking_updated)
        
        # Start consumer in background
        _consumer_task = asyncio.create_task(_consumer.start())
        logger.info("Event consumer started")
    
    yield
    
    # Cleanup using shared helper
    await cleanup_consumer(_consumer, _consumer_task, logger)
    logger.info("Resource Service stopped")

lifespan = app_lifespan

app = FastAPI(
    title="Resource Service",
    version="0.1.0",
    description="API responsável por categorias, recursos e disponibilidade.",
    openapi_tags=tags_metadata,
    root_path=_ROOT_PATH,
    lifespan=lifespan,
    docs_url=None,
    redoc_url="/redoc",
)

app.state.config = _CONFIG
app.state.settings_provider = default_settings_provider
# carrega URL do serviço tenants no docker-compose
app.state.tenant_service_url = os.getenv("TENANT_SERVICE_URL")


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
            url: '/api-docs/resources/openapi.json',
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

app.include_router(categories.router, prefix="/categories")
app.include_router(resources.router, prefix="/resources")


@app.get("/")
def root():
    return {
        "service": "resource",
        "status": "ok",
        "docs_url": "/docs",
        "config": {
            "redis_stream": _CONFIG.redis.stream,
        },
    }
