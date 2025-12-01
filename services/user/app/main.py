import os

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

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
    docs_url="/docs",
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
