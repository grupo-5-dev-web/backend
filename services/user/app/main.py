import os
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from sqlalchemy.exc import OperationalError
from app.core.database import Base, engine
from app.models import user as user_models
from app.routers import users
from shared import load_service_config
import time

tags_metadata = [
    {
        "name": "Users",
        "description": "Gerenciamento de usuários, permissões e papéis do tenant.",
    }
]

_CONFIG = load_service_config("user")
_ROOT_PATH = os.getenv("APP_ROOT_PATH", "")

app = FastAPI(
    title="User Service",
    version="0.1.0",
    description="API responsável por cadastro, atualização e desativação de usuários multi-tenant.",
    openapi_tags=tags_metadata,
    root_path=_ROOT_PATH,
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


@app.on_event("startup")
def on_startup():
    for tentativa in range(10):
        try:
            _ = user_models.User
            Base.metadata.create_all(bind=engine)
            break
        except OperationalError as exc:  # pragma: no cover
            wait_seconds = 2
            print(
                f"[User Service] Banco indisponível, aguardando {wait_seconds}s... tentativa {tentativa + 1}",
                exc,
            )
            time.sleep(wait_seconds)


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
