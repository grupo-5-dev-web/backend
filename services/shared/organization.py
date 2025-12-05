"""Shared helpers for tenant organization settings and scheduling rules."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Callable
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class OrganizationSettings:
    timezone: str
    working_hours_start: time
    working_hours_end: time
    booking_interval: int
    advance_booking_days: int
    cancellation_hours: int


_DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "UTC")
_DEFAULT_WORKING_START = os.getenv("DEFAULT_WORKING_HOURS_START", "08:00")
_DEFAULT_WORKING_END = os.getenv("DEFAULT_WORKING_HOURS_END", "18:00")
_DEFAULT_BOOKING_INTERVAL = int(os.getenv("DEFAULT_BOOKING_INTERVAL", "30"))
_DEFAULT_ADVANCE_DAYS = int(os.getenv("DEFAULT_ADVANCE_BOOKING_DAYS", "30"))
_DEFAULT_CANCELLATION_HOURS = int(os.getenv("DEFAULT_CANCELLATION_HOURS", "24"))


SettingsProvider = Callable[[UUID], OrganizationSettings]


def _parse_time(value: time | str, fallback: str) -> time:
    if isinstance(value, time):
        return value
    raw = value or fallback
    return time.fromisoformat(raw)


def _build_settings(payload: dict) -> OrganizationSettings:
    return OrganizationSettings(
        timezone=payload.get("timezone", _DEFAULT_TIMEZONE),
        working_hours_start=_parse_time(payload.get("working_hours_start"), _DEFAULT_WORKING_START),
        working_hours_end=_parse_time(payload.get("working_hours_end"), _DEFAULT_WORKING_END),
        booking_interval=int(payload.get("booking_interval", _DEFAULT_BOOKING_INTERVAL)),
        advance_booking_days=int(payload.get("advance_booking_days", _DEFAULT_ADVANCE_DAYS)),
        cancellation_hours=int(payload.get("cancellation_hours", _DEFAULT_CANCELLATION_HOURS)),
    )


def default_settings_provider(tenant_id: UUID) -> OrganizationSettings:
    base_url = os.getenv("TENANT_SERVICE_URL")
    if base_url:
        url = f"{base_url.rstrip('/')}/tenants/{tenant_id}/settings"
        try:
            response = httpx.get(url, timeout=2.0)
            response.raise_for_status()
            return _build_settings(response.json())
        except Exception:
            pass
    return _build_settings({})


def resolve_settings_provider(app_state) -> SettingsProvider:
    provider = getattr(app_state, "settings_provider", None)
    if provider is None:
        provider = default_settings_provider
        setattr(app_state, "settings_provider", provider)
    return provider


def _resolve_zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def ensure_timezone(dt: datetime, tz_name: str) -> datetime:
    zone = _resolve_zone(tz_name)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(zone)


def minutes_since_midnight(dt: datetime, tz_name: str) -> int:
    localized = ensure_timezone(dt, tz_name)
    return localized.hour * 60 + localized.minute


def validate_booking_window(start: datetime, end: datetime, settings: OrganizationSettings) -> None:
    start_local = ensure_timezone(start, settings.timezone)
    end_local = ensure_timezone(end, settings.timezone)

    if end_local <= start_local:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Horário final deve ser maior que o inicial.")

    now_utc = datetime.now(timezone.utc)
    start_utc = start_local.astimezone(timezone.utc)

    if start_utc <= now_utc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Agendamentos devem ser criados para horários futuros.")

    max_allowed = now_utc + timedelta(days=settings.advance_booking_days)
    if start_utc > max_allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Agendamentos só podem ser feitos com até {settings.advance_booking_days} dias de antecedência.",
        )

    duration_minutes = int((end_local - start_local).total_seconds() // 60)
    if duration_minutes <= 0 or duration_minutes % settings.booking_interval != 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Duração deve ser múltiplo de {settings.booking_interval} minutos.",
        )

    start_minutes = minutes_since_midnight(start_local, settings.timezone)
    end_minutes = minutes_since_midnight(end_local, settings.timezone)
    work_start = settings.working_hours_start.hour * 60 + settings.working_hours_start.minute
    work_end = settings.working_hours_end.hour * 60 + settings.working_hours_end.minute

    if start_minutes < work_start or end_minutes > work_end:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Horário fora do expediente configurado.")

    if start_minutes % settings.booking_interval != 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Horário inicial deve respeitar intervalos de {settings.booking_interval} minutos.",
        )


def validate_cancellation_window(start: datetime, settings: OrganizationSettings) -> None:
    if settings.cancellation_hours <= 0:
        return

    localized_start = ensure_timezone(start, settings.timezone)
    start_utc = localized_start.astimezone(timezone.utc)
    now_utc = datetime.now(timezone.utc)
    limit = now_utc + timedelta(hours=settings.cancellation_hours)
    if start_utc < limit:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cancelamento permitido somente até {settings.cancellation_hours} horas antes do início.",
        )


def can_cancel_booking(start: datetime, settings: OrganizationSettings) -> bool:
    if settings.cancellation_hours <= 0:
        return True

    localized_start = ensure_timezone(start, settings.timezone)
    start_utc = localized_start.astimezone(timezone.utc)
    now_utc = datetime.now(timezone.utc)
    limit = now_utc + timedelta(hours=settings.cancellation_hours)
    return start_utc >= limit