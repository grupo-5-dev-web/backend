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
    auth_token: str | None = None,
    tz_name: str | None = None,
) -> List[tuple[datetime, datetime]]:
    base_url = os.getenv("BOOKING_SERVICE_URL")
    if not base_url:
        print("[BOOKINGS] BOOKING_SERVICE_URL NÃO CONFIGURADA")
        return []

    base = base_url.rstrip("/")
    if base.endswith("/bookings"):
        url = base + "/"
    else:
        url = base + "/bookings/"

    params = {
        "tenant_id": str(tenant_id),
        "resource_id": str(resource_id),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }

    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    print("[BOOKINGS] Chamando:", url, "params=", params)

    try:
        response = httpx.get(
            url,
            params=params,
            headers=headers,
            timeout=2.0,
            follow_redirects=True,
        )
        print("[BOOKINGS] status:", response.status_code)
        print("[BOOKINGS] body:", response.text)
        response.raise_for_status()
    except Exception as e:
        print("[BOOKINGS] ERRO AO CONSULTAR:", repr(e))
        return []

    data = response.json()

    bookings: list[tuple[datetime, datetime]] = []
    for item in data:
        try:
            raw_start = str(item["start_time"])
            raw_end = str(item["end_time"])

            # se vier com "Z", trata como UTC direto
            raw_start = raw_start.replace("Z", "+00:00")
            raw_end = raw_end.replace("Z", "+00:00")

            start_dt = datetime.fromisoformat(raw_start)
            end_dt = datetime.fromisoformat(raw_end)

            if tz_name:
                # horários sem tz = horário local do tenant
                if start_dt.tzinfo is None:
                    local_start = ensure_timezone(start_dt, tz_name)
                    start_dt = local_start.astimezone(timezone.utc)
                else:
                    start_dt = start_dt.astimezone(timezone.utc)

                if end_dt.tzinfo is None:
                    local_end = ensure_timezone(end_dt, tz_name)
                    end_dt = local_end.astimezone(timezone.utc)
                else:
                    end_dt = end_dt.astimezone(timezone.utc)
            else:
                # fallback (não deve ser seu caso, mas deixo robusto)
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                else:
                    start_dt = start_dt.astimezone(timezone.utc)

                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
                else:
                    end_dt = end_dt.astimezone(timezone.utc)

            bookings.append((start_dt, end_dt))
        except Exception as exc:
            print("[BOOKINGS] ERRO PARSING ITEM:", item, "EXC:", repr(exc))
            continue

    print("[BOOKINGS] bookings encontrados:", bookings) # pra debugar
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
    auth_token: str | None = None,
) -> dict:
    """Calcula disponibilidade de recurso com cache Redis.
    
    Args:
        app_state: Estado da aplicação FastAPI
        db_session: Sessão do banco de dados
        resource_id: ID do recurso
        target_date: Data para calcular disponibilidade
        auth_token: Token de autenticação (opcional)
        
    Returns:
        Dicionário com disponibilidade do recurso
    """
    date_str = target_date.isoformat()
    
    # Tentar buscar do cache primeiro
    cache = getattr(app_state, "redis_cache", None)
    if cache is None:
        # Tentar criar cache a partir da config
        config = getattr(app_state, "config", None)
        if config and hasattr(config, "redis"):
            from shared.cache import create_redis_cache
            cache = create_redis_cache(config.redis.url)
            if cache:
                setattr(app_state, "redis_cache", cache)
    
    if cache is not None:
        from shared.cache import get_cached_availability
        cached_availability = get_cached_availability(cache, resource_id, date_str)
        if cached_availability is not None:
            return cached_availability

    resource = crud.buscar_recurso(db_session, resource_id)
    if not resource:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurso não encontrado")
    if resource.status != "disponivel":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Recurso indisponível para reservas.")

    settings_provider: SettingsProvider = resolve_settings_provider(
        app_state,
        auth_token=auth_token,
    )
    settings = settings_provider(resource.tenant_id)

    today_local = ensure_timezone(datetime.now(timezone.utc), settings.timezone).date()
    if target_date < today_local:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Data deve ser igual ou posterior a hoje.")

    if target_date > today_local + timedelta(days=settings.advance_booking_days):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Consultas de disponibilidade limitadas a {settings.advance_booking_days} dias de antecedência.",
        )

    availability_data = resource.availability_schedule or {}

    weekday_index = target_date.weekday()
    weekday_key = _WEEKDAY_KEYS[weekday_index]

    time_ranges: List[tuple[time, time]] = []

    # Formato antigo: {"monday": ["08:00-12:00", "13:00-16:00"], ...}
    if weekday_key in availability_data:
        daily_schedule = availability_data.get(weekday_key, []) or []
        for entry in daily_schedule:
            # cada entry é uma string "HH:MM-HH:MM"
            start_time, end_time = _parse_schedule_entry(entry)
            time_ranges.append((start_time, end_time))

    # Formato novo: {"schedule": [{"day_of_week": 0, "start_time": "...", "end_time": "..."}, ...]}
    elif "schedule" in availability_data:
        schedule_list = availability_data.get("schedule", []) or []
        for entry in schedule_list:
            if entry.get("day_of_week") != weekday_index:
                continue
            try:
                start_time = time.fromisoformat(entry["start_time"])
                end_time = time.fromisoformat(entry["end_time"])
            except (KeyError, ValueError) as exc:
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "Disponibilidade inválida configurada.",
                ) from exc
            if end_time <= start_time:
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "Intervalo de disponibilidade inválido.",
                )
            time_ranges.append((start_time, end_time))

    # nenhum horário configurado pra esse dia
    if not time_ranges:
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

    bookings = _collect_existing_bookings(
        resource.tenant_id,
        resource.id,
        day_start,
        day_end,
        auth_token=auth_token,
        tz_name=settings.timezone, 
    )

    slots: List[AvailabilitySlot] = []
    for start_time, end_time in time_ranges:
        slots.extend(_generate_slots(target_date, start_time, end_time, settings))

    filtered_slots = [
        slot.model_dump()
        for slot in slots
        if not _is_slot_conflicted(slot, bookings)
    ]

    result = {
        "resource_id": str(resource.id),
        "tenant_id": str(resource.tenant_id),
        "date": target_date.isoformat(),
        "timezone": settings.timezone,
        "slots": filtered_slots,
    }
    
    # Armazenar no cache se disponível
    if cache is not None:
        from shared.cache import set_cached_availability, get_cache_ttl
        ttl = get_cache_ttl("availability", default=300)
        set_cached_availability(cache, resource_id, date_str, result, ttl=ttl)
    
    return result
