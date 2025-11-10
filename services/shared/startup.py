"""Async lifespan helpers shared by FastAPI services."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Iterable, Sequence

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError
from sqlalchemy.sql.schema import MetaData


@asynccontextmanager
async def database_lifespan(
    _: FastAPI,
    *,
    service_name: str,
    metadata: MetaData,
    engine,
    models: Sequence[object] | None = None,
    retries: int = 10,
    wait_seconds: float = 2.0,
) -> None:
    """Ensure database tables exist before the service starts handling requests."""
    for attempt in range(retries):
        try:
            if models:
                _ = tuple(models)
            metadata.create_all(bind=engine)
            break
        except OperationalError as exc:  # pragma: no cover - only triggered when DB is down
            print(
                f"[{service_name}] Banco indisponível, aguardando {wait_seconds}s... tentativa {attempt + 1}",
                exc,
            )
            await asyncio.sleep(wait_seconds)
    yield


def database_lifespan_factory(
    *,
    service_name: str,
    metadata: MetaData,
    engine,
    models: Iterable[object] | None = None,
    retries: int = 10,
    wait_seconds: float = 2.0,
):
    """Return a FastAPI lifespan callable pre-configured for database initialization."""

    models_tuple = tuple(models) if models else None

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        async with database_lifespan(
            app,
            service_name=service_name,
            metadata=metadata,
            engine=engine,
            models=models_tuple,
            retries=retries,
            wait_seconds=wait_seconds,
        ):
            yield

    return _lifespan
