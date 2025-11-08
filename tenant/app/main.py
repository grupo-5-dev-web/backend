# app/main.py
from fastapi import FastAPI
from app.core.database import Base, engine
from app.routers import endpoints as tenants
from sqlalchemy.exc import OperationalError
import time

app = FastAPI(title="Tenant Service")

@app.on_event("startup")
def on_startup():
    # tenta algumas vezes até o Postgres estar pronto
    for tentativa in range(10):
        try:
            print("Tentando criar tabelas do Tenant... tentativa", tentativa + 1)
            Base.metadata.create_all(bind=engine)
            print("Tabelas criadas com sucesso!")
            break
        except OperationalError as e:
            print("Banco ainda não está pronto, aguardando 2s...", str(e))
            time.sleep(2)

# add as rotas definidas em endpoints.py aqui, pq aí as urls funcionam
app.include_router(tenants.router, prefix="/tenants", tags=["Tenants"])

@app.get("/")
def root():
    return {"message": "Tenant Service ta funcionando :)"}
