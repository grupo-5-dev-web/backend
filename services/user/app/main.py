import os

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse

from app.core.database import Base, engine
from app.models import user as user_models
from app.routers import users
from shared import database_lifespan_factory, load_service_config

tags_metadata = [
    {
        "name": "Users",
        "description": "Gerenciamento de usuários, permissões e papéis do tenant.",
    }
]

_CONFIG = load_service_config("user")
_ROOT_PATH = os.getenv("APP_ROOT_PATH", "")

lifespan = database_lifespan_factory(
    service_name="User Service",
    metadata=Base.metadata,
    engine=engine,
    models=(user_models.User,),
)

app = FastAPI(
    title="User Service",
    version="0.1.0",
    description="API responsável por cadastro, atualização e desativação de usuários multi-tenant.",
    openapi_tags=tags_metadata,
    root_path=_ROOT_PATH,
    lifespan=lifespan,
    docs_url=None,
    redoc_url="/redoc",
)

app.state.config = _CONFIG


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
        <title>{app.title} - Swagger UI</title>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
        const ui = SwaggerUIBundle({{
            url: '/api-docs/users/openapi.json',
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
app.include_router(users.router)


@app.get("/")
def root():
    return {
        "service": "user",
        "status": "ok",
        "docs_url": "/docs",
        "config": {
            "redis_stream": _CONFIG.redis.stream,
        },
    }
