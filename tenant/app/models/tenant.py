# app/models/tenant.py
from sqlalchemy import Column, Integer, String
from app.core.database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    dominio = Column(String, unique=True, nullable=False)
    logo = Column(String, nullable=False) # url da logo
    tema_cor = Column(String, nullable=False) # em hexadecimal
    plano = Column(String, nullable=False) # tipo do plano
