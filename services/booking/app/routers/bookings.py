from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from app.services.tenant_validator import validar_tenant_existe
from app.services.resource_validator import validar_recurso_existe
from app.services.user_validator import validar_usuario_existe
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
            "description": "Violação das regras de reserva (horário, antecedência, intervalo).",
        },
        status.HTTP_409_CONFLICT: {
            "model": BookingConflictResponse,
            "description": "Conflito com outra reserva do mesmo recurso.",
        },
    },
)
async def create_booking(
    payload: BookingCreate,
    request: Request,
    db: Session = Depends(get_db),
):

    tenant_service = request.app.state.tenant_service_url
    resource_service = request.app.state.resource_service_url
    user_service = request.app.state.user_service_url

    await validar_tenant_existe(tenant_service, str(payload.tenant_id))
    recurso_data = await validar_recurso_existe(resource_service, str(payload.resource_id))

    if str(recurso_data["tenant_id"]) != str(payload.tenant_id):
        raise HTTPException(
            status_code=400,
            detail="Recurso não pertence ao Tenant informado"
        )
        
    usuario_data = await validar_usuario_existe(user_service, str(payload.user_id))

    # verifica se usuário pertence ao mesmo tenant da reserva
    if str(usuario_data["tenant_id"]) != str(payload.tenant_id):
        raise HTTPException(
            status_code=400,
            detail="Usuário não pertence ao Tenant informado"
        )

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
        return JSONResponse(
            status_code=409,
            content=conflict_payload.model_dump(mode="json"),
        )

    publisher = getattr(request.app.state, "event_publisher", None)
    booking = crud.create_booking(db, payload, publisher=publisher)
    return booking


@router.get("/", response_model=List[BookingWithPolicy])
def list_bookings(
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
    
    if not bookings:
        # por especificidade
        if resource_id:
            raise HTTPException(
                status_code=404,
                detail="Não foram encontradas reservas para este Recurso."
            )
        if user_id:
            raise HTTPException(
                status_code=404,
                detail="Não foram encontradas reservas para este Usuário."
            )
        if status_param:
            raise HTTPException(
                status_code=404,
                detail=f"Não foram encontradas reservas com status '{status_param}'."
            )
        if start_dt or end_dt:
            raise HTTPException(
                status_code=404,
                detail="Nenhuma reserva encontrada no período informado."
            )

        # fallback: apenas tenant
        raise HTTPException(
            status_code=404,
            detail="Não foram encontradas reservas neste Tenant ou ele não existe."
        )

    # enriquecimento da resposta
    settings_provider = resolve_settings_provider(request.app.state)
    settings = settings_provider(tenant_id)

    enriched: List[BookingWithPolicy] = []
    for item in bookings:
        base_data = BookingOut.model_validate(item).model_dump(mode="python")
        enriched.append(
            BookingWithPolicy(
                **base_data, 
                can_cancel=can_cancel_booking(item.start_time, settings)
            )
        )

    return enriched


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: UUID, db: Session = Depends(get_db)):
    booking = crud.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva não encontrada")
    return booking


@router.put(
    "/{booking_id}",
    response_model=BookingOut,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Violação das regras de reserva (horário, antecedência, intervalo).",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Reserva não encontrada.",
        },
        status.HTTP_409_CONFLICT: {
            "model": BookingConflictResponse,
            "description": "Conflito com outra reserva do mesmo recurso.",
        },
    },
)
def update_booking(
    booking_id: UUID,
    payload: BookingUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    booking = crud.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva não encontrada")

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
                message="Recurso já possui reserva neste intervalo",
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
            "description": "Reserva não encontrada.",
        },
    },
)
def cancel_booking(
    booking_id: UUID,
    cancel_payload: BookingCancelRequest,
    request: Request,
    cancelled_by: UUID = Query(..., description="Usuário responsável pelo cancelamento"),
    db: Session = Depends(get_db),
):
    booking = crud.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva não encontrada")

    settings_provider = resolve_settings_provider(request.app.state)
    settings = settings_provider(booking.tenant_id)
    validate_cancellation_window(booking.start_time, settings)

    publisher = getattr(request.app.state, "event_publisher", None)
    cancelled = crud.cancel_booking(db, booking_id, cancelled_by, cancel_payload.reason, publisher=publisher)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Reserva não encontrada")
    return cancelled


@router.patch(
    "/{booking_id}/status",
    response_model=BookingOut,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Status fornecido é inválido.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Reserva não encontrada.",
        },
    },
)
def update_status(
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
        raise HTTPException(status_code=404, detail="Reserva não encontrada")
    return booking
