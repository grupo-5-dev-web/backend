"""Configuration helpers reused by microservices."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Dict

_DEFAULT_DATABASE_URLS: Dict[str, str] = {
    "tenant": "postgresql://user:password@db_tenant:5432/tenantdb",
    "resource": "postgresql://user:password@db_resource:5432/resourcedb",
    "booking": "postgresql://user:password@db_booking:5432/bookingdb",
    "user": "postgresql://user:password@db_user:5432/userdb",
}

_DEFAULT_REDIS_URL = "redis://redis:6379/0"
_DEFAULT_EVENT_STREAM = "booking-events"
_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 8000


@dataclass(frozen=True)
class DatabaseConfig:
    url: str


@dataclass(frozen=True)
class RedisConfig:
    url: str
    stream: str


@dataclass(frozen=True)
class ServiceConfig:
    name: str
    host: str
    port: int
    database: DatabaseConfig
    redis: RedisConfig


def _lookup_database_url(service_name: str) -> str:
    service_env = f"{service_name.upper()}_DATABASE_URL"
    return (
        os.getenv(service_env)
        or os.getenv("DATABASE_URL")
        or _DEFAULT_DATABASE_URLS.get(service_name, "")
    )


def load_service_config(service_name: str) -> ServiceConfig:
    """Aggregate configuration for a given service using env vars with sane fallbacks."""

    normalized_name = service_name.lower()
    db_url = _lookup_database_url(normalized_name)
    if not db_url:
        raise ValueError(
            f"DATABASE_URL not configured for service '{normalized_name}'. "
            "Set DATABASE_URL or {normalized_name.upper()}_DATABASE_URL."
        )

    host = os.getenv("APP_HOST", _DEFAULT_HOST)
    port = int(os.getenv("APP_PORT", str(_DEFAULT_PORT)))

    redis_url = os.getenv("REDIS_URL", _DEFAULT_REDIS_URL)
    stream_name = os.getenv("EVENT_STREAM", _DEFAULT_EVENT_STREAM)

    return ServiceConfig(
        name=normalized_name,
        host=host,
        port=port,
        database=DatabaseConfig(url=db_url),
        redis=RedisConfig(url=redis_url, stream=stream_name),
    )
