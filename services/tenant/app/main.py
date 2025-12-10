# app/main.py
import os
from html import escape

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse

from app.core.database import Base, engine
from app.models import tenant as tenant_models
from app.routers import endpoints as tenants
from shared import database_lifespan_factory, load_service_config, EventPublisher

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

lifespan = database_lifespan_factory(
    service_name="Tenant Service",
    metadata=Base.metadata,
    engine=engine,
    models=(tenant_models.Tenant, tenant_models.OrganizationSettings),
)

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
            url: '/api-docs/tenants/openapi.json',
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

# add as rotas definidas em endpoints.py aqui, pq aí as urls funcionam
app.include_router(tenants.router, prefix="/tenants")

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
