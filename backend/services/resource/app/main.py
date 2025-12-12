import os

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.database import Base, engine
from app.models import resource as resource_models
from app.routers import categories, resources
from shared import (
    RequestContextLogMiddleware,
    configure_logging,
    database_lifespan_factory,
    default_settings_provider,
    load_service_config,
)

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
_LOGGER = configure_logging("resource")

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
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.config = _CONFIG
app.state.settings_provider = default_settings_provider
app.add_middleware(RequestContextLogMiddleware, logger=_LOGGER)


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


app.include_router(categories.router)
app.include_router(resources.router)


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
