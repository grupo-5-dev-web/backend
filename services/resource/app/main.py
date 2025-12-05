import os
from html import escape

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse

from app.core.database import Base, engine
from app.models import resource as resource_models
from app.routers import categories, resources
from shared import database_lifespan_factory, default_settings_provider, load_service_config

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

lifespan = database_lifespan_factory(
    service_name="Resource Service",
    metadata=Base.metadata,
    engine=engine,
    models=(resource_models.ResourceCategory, resource_models.Resource),
)

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
