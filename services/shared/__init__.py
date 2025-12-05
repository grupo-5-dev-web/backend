"""Shared utilities used across microservices."""

from .config import ServiceConfig, load_service_config
from .messaging import EventPublisher
from .event_consumer import EventConsumer, cleanup_consumer
from .organization import (
    OrganizationSettings,
    SettingsProvider,
    default_settings_provider,
    ensure_timezone,
    minutes_since_midnight,
    resolve_settings_provider,
    validate_booking_window,
    validate_cancellation_window,
    can_cancel_booking,
)
from .startup import database_lifespan, database_lifespan_factory

__all__ = [
    "ServiceConfig",
    "load_service_config",
    "EventPublisher",
    "EventConsumer",
    "cleanup_consumer",
    "OrganizationSettings",
    "SettingsProvider",
    "default_settings_provider",
    "resolve_settings_provider",
    "validate_booking_window",
    "validate_cancellation_window",
    "can_cancel_booking",
    "ensure_timezone",
    "minutes_since_midnight",
    "database_lifespan",
    "database_lifespan_factory",
]
