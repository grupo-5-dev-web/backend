from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from shared import load_service_config

_config = load_service_config("user")

engine = create_engine(
    _config.database.url,
    future=True,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
