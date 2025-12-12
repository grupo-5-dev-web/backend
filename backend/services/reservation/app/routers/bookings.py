from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
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

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def _parse_iso_datetime(value: Optional[str], field_name: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        sanitized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(sanitized)
    except ValueError as exc:  # pragma: no cover - validação simples
        raise HTTPException(status_code=400, detail=f"{field_name} inválido") from exc


@router.post(
    "/",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Violação das regras de agendamento (horário, antecedência, intervalo).",
        },
        status.HTTP_409_CONFLICT: {
            "model": BookingConflictResponse,
            "description": "Conflito com outro agendamento do mesmo recurso.",
        },
    },
)
def create_booking_endpoint(
    payload: BookingCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    settings_provider = resolve_settings_provider(request.app.state)
    settings = settings_provider(payload.tenant_id)
    validate_booking_window(payload.start_time, payload.end_time, settings)

    conflicts = crud.find_conflicts(
        db,
        payload.tenant_id,
        payload.resource_id,
        payload.start_time,
        payload.end_time,
    )
    if conflicts:
        conflict_payload = BookingConflictResponse(
            success=False,
            error="conflict",
            message="Recurso já possui agendamento neste intervalo",
            conflicts=[
                BookingConflict(
                    booking_id=booking.id,
                    start_time=booking.start_time,
                    end_time=booking.end_time,
                )
                for booking in conflicts
            ],
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=conflict_payload.model_dump(mode="json"),
        )

    publisher = getattr(request.app.state, "event_publisher", None)
    booking = crud.create_booking(db, payload, publisher=publisher)
    return booking


@router.get("/", response_model=List[BookingWithPolicy])
def list_bookings_endpoint(
    request: Request,
    tenant_id: UUID = Query(...),
    resource_id: Optional[UUID] = Query(default=None),
    user_id: Optional[UUID] = Query(default=None),
    status_param: Optional[str] = Query(default=None, alias="status"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    start_dt = _parse_iso_datetime(start_date, "start_date")
    end_dt = _parse_iso_datetime(end_date, "end_date")

    if status_param and status_param not in BookingStatus.ALL:
        raise HTTPException(status_code=400, detail="Status inválido")

    bookings = crud.list_bookings(
        db=db,
        tenant_id=tenant_id,
        resource_id=resource_id,
        user_id=user_id,
        status=status_param,
        start_date=start_dt,
        end_date=end_dt,
    )
    settings_provider = resolve_settings_provider(request.app.state)
    settings = settings_provider(tenant_id)

    enriched: List[BookingWithPolicy] = []
    for item in bookings:
        base_data = BookingOut.model_validate(item).model_dump(mode="python")
        enriched.append(
            BookingWithPolicy(**base_data, can_cancel=can_cancel_booking(item.start_time, settings))
        )
    return enriched


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking_endpoint(booking_id: UUID, db: Session = Depends(get_db)):
    booking = crud.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    return booking


@router.put(
    "/{booking_id}",
    response_model=BookingOut,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Violação das regras de agendamento (horário, antecedência, intervalo).",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Agendamento não encontrado.",
        },
        status.HTTP_409_CONFLICT: {
            "model": BookingConflictResponse,
            "description": "Conflito com outro agendamento do mesmo recurso.",
        },
    },
)
def update_booking_endpoint(
    booking_id: UUID,
    payload: BookingUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    booking = crud.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    settings_provider = resolve_settings_provider(request.app.state)
    settings = settings_provider(booking.tenant_id)

    new_start = payload.start_time or booking.start_time
    new_end = payload.end_time or booking.end_time

    if payload.start_time or payload.end_time or payload.resource_id:
        validate_booking_window(new_start, new_end, settings)

        conflicts = crud.find_conflicts(
            db,
            booking.tenant_id,
            payload.resource_id or booking.resource_id,
            new_start,
            new_end,
            ignore_booking_id=booking_id,
        )
        if conflicts:
            conflict_payload = BookingConflictResponse(
                success=False,
                error="conflict",
                message="Recurso já possui agendamento neste intervalo",
                conflicts=[
                    BookingConflict(
                        booking_id=item.id,
                        start_time=item.start_time,
                        end_time=item.end_time,
                    )
                    for item in conflicts
                ],
            )
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=conflict_payload.model_dump(mode="json"),
            )

    publisher = getattr(request.app.state, "event_publisher", None)
    updated_booking = crud.update_booking(db, booking_id, payload, publisher=publisher)
    return updated_booking


@router.patch(
    "/{booking_id}/cancel",
    response_model=BookingOut,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Cancelamento fora da janela permitida.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Agendamento não encontrado.",
        },
    },
)
def cancel_booking_endpoint(
    booking_id: UUID,
    cancel_payload: BookingCancelRequest,
    request: Request,
    cancelled_by: UUID = Query(..., description="Usuário responsável pelo cancelamento"),
    db: Session = Depends(get_db),
):
    booking = crud.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    settings_provider = resolve_settings_provider(request.app.state)
    settings = settings_provider(booking.tenant_id)
    validate_cancellation_window(booking.start_time, settings)

    publisher = getattr(request.app.state, "event_publisher", None)
    cancelled = crud.cancel_booking(db, booking_id, cancelled_by, cancel_payload.reason, publisher=publisher)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    return cancelled


@router.patch(
    "/{booking_id}/status",
    response_model=BookingOut,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Status fornecido é inválido.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Agendamento não encontrado.",
        },
    },
)
def update_status_endpoint(
    booking_id: UUID,
    request: Request,
    status_param: str = Query(..., description="Novo status"),
    db: Session = Depends(get_db),
):
    if status_param not in BookingStatus.ALL:
        raise HTTPException(status_code=400, detail="Status inválido")

    publisher = getattr(request.app.state, "event_publisher", None)
    booking = crud.update_booking_status(db, booking_id, status_param, publisher=publisher)
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    return booking
