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
    except ValueError as exc:
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
        print("[BOOKINGS] BOOKING_SERVICE_URL NÃO CONFIGURADA")
        return []

    url = f"{base_url.rstrip('/')}/"
    params = {
        "tenant_id": str(tenant_id),
        "resource_id": str(resource_id),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }

    print("[BOOKINGS] Chamando:", url, "params=", params)

    try:
        response = httpx.get(url, params=params, timeout=2.0)
        print("[BOOKINGS] status:", response.status_code)
        print("[BOOKINGS] body:", response.text)
        response.raise_for_status()
    except Exception as e:
        print("[BOOKINGS] ERRO AO CONSULTAR:", repr(e))
        return []

    data = response.json()

    bookings = []
    for item in data:
        start_dt = datetime.fromisoformat(item["start_time"].replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(item["end_time"].replace("Z", "+00:00"))
        bookings.append((start_dt, end_dt))

    print("[BOOKINGS] bookings encontrados:", bookings)
    return bookings


def _is_slot_conflicted(slot, bookings):
    slot_start_utc = slot.start.astimezone(timezone.utc)
    slot_end_utc = slot.end.astimezone(timezone.utc)

    for booking_start, booking_end in bookings:
        if booking_start < slot_end_utc and booking_end > slot_start_utc:
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

    # Suporta o novo formato com schedule array
    availability_data = resource.availability_schedule or {}
    schedule_list = availability_data.get("schedule", [])
    
    # Filtrar entradas para o dia da semana correto (0=segunda, 6=domingo)
    target_weekday = target_date.weekday()
    daily_schedule = [
        entry for entry in schedule_list 
        if entry.get("day_of_week") == target_weekday
    ]
    
    if not daily_schedule:
        return {
            "resource_id": str(resource.id),
            "tenant_id": str(resource.tenant_id),
            "date": target_date.isoformat(),
            "timezone": settings.timezone,
            "slots": [],
        }

    local_zone = ensure_timezone(datetime.now(timezone.utc), settings.timezone).tzinfo

    day_start_local = datetime.combine(target_date, time.min, tzinfo=local_zone)
    day_end_local = datetime.combine(target_date, time.max, tzinfo=local_zone)

    day_start = day_start_local.astimezone(timezone.utc)
    day_end = day_end_local.astimezone(timezone.utc)

    bookings = _collect_existing_bookings(resource.tenant_id, resource.id, day_start, day_end)

    slots: List[AvailabilitySlot] = []
    for entry in daily_schedule:
        # No novo formato, start_time e end_time já estão como campos separados
        start_time = time.fromisoformat(entry["start_time"])
        end_time = time.fromisoformat(entry["end_time"])
        slots.extend(_generate_slots(target_date, start_time, end_time, settings))

    filtered_slots = [slot.model_dump() for slot in slots if not _is_slot_conflicted(slot, bookings)]

    return {
        "resource_id": str(resource.id),
        "tenant_id": str(resource.tenant_id),
        "date": target_date.isoformat(),
        "timezone": settings.timezone,
        "slots": filtered_slots,
    }
