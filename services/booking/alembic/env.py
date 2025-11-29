from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

SERVICE_NAME = "booking"

BASE_DIR = Path(__file__).resolve().parent
SERVICE_DIR = BASE_DIR.parent
REPO_DIR = SERVICE_DIR.parent

sys.path.append(str(SERVICE_DIR))
sys.path.append(str(REPO_DIR))

from app.core.database import Base  # noqa: E402
from shared import load_service_config  # noqa: E402

config = context.config
service_config = load_service_config(SERVICE_NAME)
config.set_main_option("sqlalchemy.url", service_config.database.url)

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
