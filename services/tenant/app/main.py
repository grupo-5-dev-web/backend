# app/main.py
import os
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from sqlalchemy.exc import OperationalError
from app.core.database import Base, engine
from app.models import tenant as tenant_models
from app.routers import endpoints as tenants
from shared import load_service_config
import time

tags_metadata = [
    {
        "name": "Tenants",
        "description": "Gerenciamento de organizações white label e respectivas configurações de agenda.",
    }
]

_CONFIG = load_service_config("tenant")
_ROOT_PATH = os.getenv("APP_ROOT_PATH", "")

app = FastAPI(
    title="Tenant Service",
    version="0.1.0",
    description="API responsável pela administração de tenants e políticas globais de agendamento.",
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
    # tenta algumas vezes até o Postgres estar pronto
    for tentativa in range(10):
        try:
            print("Tentando criar tabelas do Tenant... tentativa", tentativa + 1)
            _ = (tenant_models.Tenant, tenant_models.OrganizationSettings)
            Base.metadata.create_all(bind=engine)
            print("Tabelas criadas com sucesso!")
            break
        except OperationalError as e:
            print("Banco ainda não está pronto, aguardando 2s...", str(e))
            time.sleep(2)

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
