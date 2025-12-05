from datetime import datetime, timezone, time
from shared import ensure_timezone
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.services.tenant_validator import validar_tenant_existe
from app.services.resource_validator import validar_recurso_existe
from app.services.user_validator import validar_usuario_existe
from app.core.database import get_db
from app.models.booking import BookingStatus
from app.schemas.booking_schema import (
    BookingCancelRequest,
    BookingConflict,
    BookingConflictResponse,
    BookingCreate,
    BookingOut,
    BookingUpdate,
    BookingWithPolicy,
)
from app.services.organization import (
    resolve_settings_provider,
    validate_booking_window,
    validate_cancellation_window,
    can_cancel_booking,
)
from . import crud
import os

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def is_testing() -> bool:
    return os.getenv("PYTEST_CURRENT_TEST") is not None


def _parse_iso_datetime(value: Optional[str], field_name: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        sanitized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(sanitized)
    except ValueError as exc:
        raise HTTPException(400, f"{field_name} inválido") from exc


@router.post("/", response_model=BookingOut, status_code=201)
async def create_booking(
    payload: BookingCreate,
    request: Request,
    db: Session = Depends(get_db),
):

    tenant_service = request.app.state.tenant_service_url
    resource_service = request.app.state.resource_service_url
    user_service = request.app.state.user_service_url

    # SETTINGS primeiro: precisamos do timezone do tenant
    settings_provider = resolve_settings_provider(request.app.state)
    settings = settings_provider(payload.tenant_id)

    # descobre o fuso do tenant (ex.: America/Recife)
    zone = ensure_timezone(datetime.now(timezone.utc), settings.timezone).tzinfo

    # interpretar o input SEM TZ como horário local do tenant
    if payload.start_time.tzinfo is None:
        start_local = payload.start_time.replace(tzinfo=zone)
    else:
        start_local = payload.start_time.astimezone(zone)

    if payload.end_time.tzinfo is None:
        end_local = payload.end_time.replace(tzinfo=zone)
    else:
        end_local = payload.end_time.astimezone(zone)

    # validações externas
    if not is_testing():
        await validar_tenant_existe(tenant_service, str(payload.tenant_id))
        recurso_data = await validar_recurso_existe(resource_service, str(payload.resource_id))

        if str(recurso_data["tenant_id"]) != str(payload.tenant_id):
            raise HTTPException(400, "Recurso não pertence ao Tenant informado")

        usuario_data = await validar_usuario_existe(user_service, str(payload.user_id))
        if str(usuario_data["tenant_id"]) != str(payload.tenant_id):
            raise HTTPException(400, "Usuário não pertence ao Tenant informado")

        # validar contra availability_schedule do recurso
        schedule = recurso_data.get("availability_schedule", {})
        weekday = start_local.weekday()  # 0 = Monday
        weekday_key = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][weekday]

        allowed_ranges = schedule.get(weekday_key, [])

        if not allowed_ranges:
            raise HTTPException(400, "Recurso indisponível neste dia da semana.")

        valid = False
        for rng in allowed_ranges:
            start_raw, end_raw = rng.split("-")
            r_start = datetime.combine(start_local.date(), time.fromisoformat(start_raw), tzinfo=zone)
            r_end = datetime.combine(start_local.date(), time.fromisoformat(end_raw), tzinfo=zone)

            # o intervalo pedido precisa CABER dentro de algum range permitido
            if start_local >= r_start and end_local <= r_end:
                valid = True
                break

        if not valid:
            raise HTTPException(400, "Horário não permitido na disponibilidade do recurso.")

    # validações de janela (futuro, duração, expediente, etc.) em HORÁRIO LOCAL
    validate_booking_window(start_local, end_local, settings)

    # conflito: comparamos em UTC
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    conflicts = crud.find_conflicts(
        db,
        payload.tenant_id,
        payload.resource_id,
        start_utc,
        end_utc,
    )

    if conflicts:
        conflict_payload = BookingConflictResponse(
            success=False,
            error="conflict",
            message="Recurso já possui reserva neste intervalo",
            conflicts=[
                BookingConflict(
                    booking_id=b.id,
                    start_time=b.start_time,
                    end_time=b.end_time,
                )
                for b in conflicts
            ],
        )
        return JSONResponse(status_code=409, content=conflict_payload.model_dump(mode="json"))

    # salvar em UTC
    payload.start_time = start_utc
    payload.end_time = end_utc

    publisher = getattr(request.app.state, "event_publisher", None)
    booking = crud.create_booking(db, payload, publisher=publisher)
    return booking


@router.get("/", response_model=List[BookingWithPolicy])
def list_bookings(
    request: Request,
    tenant_id: UUID = Query(...),
    resource_id: Optional[UUID] = Query(None),
    user_id: Optional[UUID] = Query(None),
    status_param: Optional[str] = Query(None, alias="status"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    start_dt = _parse_iso_datetime(start_date, "start_date")
    end_dt = _parse_iso_datetime(end_date, "end_date")

    if status_param and status_param not in BookingStatus.ALL:
        raise HTTPException(400, "Status inválido")

    bookings = crud.list_bookings(
        db=db,
        tenant_id=tenant_id,
        resource_id=resource_id,
        user_id=user_id,
        status=status_param,
        start_date=start_dt,
        end_date=end_dt,
    )

    if not bookings:
        raise HTTPException(404, "Nenhuma reserva encontrada.")

    settings_provider = resolve_settings_provider(request.app.state)
    settings = settings_provider(tenant_id)

    enriched = []
    for item in bookings:
        base_data = BookingOut.model_validate(item).model_dump(mode="python")
        enriched.append(
            BookingWithPolicy(
                **base_data,
                can_cancel=can_cancel_booking(item.start_time, settings),
            )
        )

    return enriched


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: UUID, db: Session = Depends(get_db)):
    booking = crud.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(404, "Reserva não encontrada")
    return booking


@router.put("/{booking_id}", response_model=BookingOut)
def update_booking(
    booking_id: UUID,
    payload: BookingUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    booking = crud.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(404, "Reserva não encontrada")

    settings_provider = resolve_settings_provider(request.app.state)
    settings = settings_provider(booking.tenant_id)
    zone = ensure_timezone(datetime.now(timezone.utc), settings.timezone).tzinfo

    new_start = payload.start_time or booking.start_time
    new_end = payload.end_time or booking.end_time

    # interpretar como horário local do tenant
    if new_start.tzinfo is None:
        new_start_local = new_start.replace(tzinfo=zone)
    else:
        new_start_local = new_start.astimezone(zone)

    if new_end.tzinfo is None:
        new_end_local = new_end.replace(tzinfo=zone)
    else:
        new_end_local = new_end.astimezone(zone)

    validate_booking_window(new_start_local, new_end_local, settings)

    new_start_utc = new_start_local.astimezone(timezone.utc)
    new_end_utc = new_end_local.astimezone(timezone.utc)

    conflicts = crud.find_conflicts(
        db,
        booking.tenant_id,
        payload.resource_id or booking.resource_id,
        new_start_utc,
        new_end_utc,
        ignore_booking_id=booking_id,
    )

    if conflicts:
        conflict_payload = BookingConflictResponse(
            success=False,
            error="conflict",
            message="Recurso já possui reserva neste intervalo",
            conflicts=[
                BookingConflict(
                    booking_id=i.id,
                    start_time=i.start_time,
                    end_time=i.end_time,
                )
                for i in conflicts
            ],
        )
        return JSONResponse(409, conflict_payload.model_dump(mode="json"))

    payload.start_time = new_start_utc
    payload.end_time = new_end_utc

    publisher = getattr(request.app.state, "event_publisher", None)
    updated = crud.update_booking(db, booking_id, payload, publisher=publisher)

    return updated


@router.patch("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: UUID,
    cancel_payload: BookingCancelRequest,
    request: Request,
    cancelled_by: UUID = Query(...),
    db: Session = Depends(get_db),
):
    booking = crud.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(404, "Reserva não encontrada")

    settings_provider = resolve_settings_provider(request.app.state)
    settings = settings_provider(booking.tenant_id)
    validate_cancellation_window(booking.start_time, settings)

    publisher = getattr(request.app.state, "event_publisher", None)
    return crud.cancel_booking(db, booking_id, cancelled_by, cancel_payload.reason, publisher=publisher)


@router.patch("/{booking_id}/status", response_model=BookingOut)
def update_status(
    booking_id: UUID,
    request: Request,
    status_param: str = Query(...),
    db: Session = Depends(get_db),
):
    if status_param not in BookingStatus.ALL:
        raise HTTPException(400, "Status inválido")

    publisher = getattr(request.app.state, "event_publisher", None)
    booking = crud.update_booking_status(db, booking_id, status_param, publisher=publisher)
    if not booking:
        raise HTTPException(404, "Reserva não encontrada")
    return booking
