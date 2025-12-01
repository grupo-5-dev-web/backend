from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, List
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from shared import (
    OrganizationSettings,
    SettingsProvider,
    ensure_timezone,
    resolve_settings_provider,
)

from app.routers import crud

_WEEKDAY_KEYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


class AvailabilitySlot:
    __slots__ = ("start", "end")

    def __init__(self, start: datetime, end: datetime) -> None:
        self.start = start
        self.end = end

    def model_dump(self) -> dict:
        return {
            "start_time": self.start.isoformat(),
            "end_time": self.end.isoformat(),
        }


def _parse_schedule_entry(entry: str) -> tuple[time, time]:
    try:
        start_raw, end_raw = entry.split("-", maxsplit=1)
        start_time = time.fromisoformat(start_raw)
        end_time = time.fromisoformat(end_raw)
    except ValueError as exc:  # pragma: no cover - proteção de dados inválidos
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Disponibilidade inválida configurada.") from exc
    if end_time <= start_time:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Intervalo de disponibilidade inválido.")
    return start_time, end_time


def _generate_slots(
    base_day: date,
    start_time: time,
    end_time: time,
    settings: OrganizationSettings,
) -> Iterable[AvailabilitySlot]:
    tz_name = settings.timezone
    zone = ensure_timezone(datetime.combine(base_day, time.min), tz_name).tzinfo or timezone.utc

    # Alinhar com janelas de trabalho do tenant
    work_start = datetime.combine(base_day, settings.working_hours_start, tzinfo=zone)
    work_end = datetime.combine(base_day, settings.working_hours_end, tzinfo=zone)

    slot_start = datetime.combine(base_day, start_time, tzinfo=zone)
    slot_end = datetime.combine(base_day, end_time, tzinfo=zone)

    if slot_start < work_start:
        slot_start = work_start
    if slot_end > work_end:
        slot_end = work_end

    if slot_end <= slot_start:
        return []

    interval = timedelta(minutes=settings.booking_interval)
    now_boundary = datetime.now(zone)

    cursor = slot_start
    # Garantir alinhamento com o intervalo do tenant
    remainder = (cursor - work_start) % interval
    if remainder:
        cursor += interval - remainder

    while cursor + interval <= slot_end:
        if cursor >= now_boundary:
            yield AvailabilitySlot(cursor, cursor + interval)
        cursor += interval


def _collect_existing_bookings(
    tenant_id: UUID,
    resource_id: UUID,
    start: datetime,
    end: datetime,
) -> List[tuple[datetime, datetime]]:
    base_url = os.getenv("BOOKING_SERVICE_URL")
    if not base_url:
        return []

    url = f"{base_url.rstrip('/')}/bookings/"
    params = {
        "tenant_id": str(tenant_id),
        "resource_id": str(resource_id),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    try:
        response = httpx.get(url, params=params, timeout=2.0)
        response.raise_for_status()
    except Exception:
        return []

    bookings = []
    for item in response.json():
        try:
            start = datetime.fromisoformat(item["start_time"])
            end = datetime.fromisoformat(item["end_time"])
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            bookings.append((start, end))
        except (KeyError, ValueError):
            continue
    return bookings


def _is_slot_conflicted(slot: AvailabilitySlot, bookings: List[tuple[datetime, datetime]]) -> bool:
    for start, end in bookings:
        if start < slot.end and end > slot.start:
            return True
    return False


def compute_availability(
    *,
    app_state,
    db_session,
    resource_id: UUID,
    target_date: date,
) -> dict:
    resource = crud.buscar_recurso(db_session, resource_id)
    if not resource:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurso não encontrado")
    if resource.status != "disponivel":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Recurso indisponível para reservas.")

    settings_provider: SettingsProvider = resolve_settings_provider(app_state)
    settings = settings_provider(resource.tenant_id)

    today_local = ensure_timezone(datetime.now(timezone.utc), settings.timezone).date()
    if target_date < today_local:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Data deve ser igual ou posterior a hoje.")

    if target_date > today_local + timedelta(days=settings.advance_booking_days):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Consultas de disponibilidade limitadas a {settings.advance_booking_days} dias de antecedência.",
        )

    weekday_key = _WEEKDAY_KEYS[target_date.weekday()]
    daily_schedule = (resource.availability_schedule or {}).get(weekday_key, [])
    if not daily_schedule:
        return {
            "resource_id": str(resource.id),
            "tenant_id": str(resource.tenant_id),
            "date": target_date.isoformat(),
            "timezone": settings.timezone,
            "slots": [],
        }

    day_start = ensure_timezone(datetime.combine(target_date, time.min, tzinfo=timezone.utc), settings.timezone)
    day_end = ensure_timezone(datetime.combine(target_date, time.max, tzinfo=timezone.utc), settings.timezone)
    bookings = _collect_existing_bookings(resource.tenant_id, resource.id, day_start, day_end)

    slots: List[AvailabilitySlot] = []
    for entry in daily_schedule:
        start_time, end_time = _parse_schedule_entry(entry)
        slots.extend(_generate_slots(target_date, start_time, end_time, settings))

    filtered_slots = [slot.model_dump() for slot in slots if not _is_slot_conflicted(slot, bookings)]

    return {
        "resource_id": str(resource.id),
        "tenant_id": str(resource.tenant_id),
        "date": target_date.isoformat(),
        "timezone": settings.timezone,
        "slots": filtered_slots,
    }