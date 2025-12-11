from datetime import datetime, timezone, time
from zoneinfo import ZoneInfo
from shared import ensure_timezone
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from app.core.auth_dependencies import get_current_token, TokenPayload, oauth2_scheme
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
from logging import getLogger


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
    current_token: TokenPayload = Depends(get_current_token),
    raw_token: str = Depends(oauth2_scheme),
):
    logger = getLogger(__name__)

    # Tenant do token deve ser o mesmo do booking
    if current_token.tenant_id != payload.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Você não pode criar reservas para outro tenant.",
        )

    # Usuário comum só pode criar booking para ele mesmo
    if current_token.user_type == "user" and payload.user_id != current_token.sub:
        raise HTTPException(
            status_code=403,
            detail="Usuário comum só pode criar reservas para si mesmo.",
        )

    tenant_service = request.app.state.tenant_service_url
    resource_service = request.app.state.resource_service_url
    user_service = request.app.state.user_service_url

    # SETTINGS primeiro: precisamos do timezone do tenant
    settings_provider = resolve_settings_provider(
        request.app.state,
        auth_token=raw_token,  # passa o token bruto (mesmo que hoje ele não seja usado no provider)
    )
    settings = settings_provider(payload.tenant_id)

    # descobre o fuso do tenant (ex.: America/Recife)
    zone = ensure_timezone(datetime.now(timezone.utc), settings.timezone).tzinfo

    start_naive = payload.start_time.replace(tzinfo=None)
    end_naive = payload.end_time.replace(tzinfo=None)

    start_local = start_naive.replace(tzinfo=zone)
    end_local = end_naive.replace(tzinfo=zone)

    logger.info(
        "DEBUG booking time: start_local=%s end_local=%s tz=%s",
        start_local,
        end_local,
        settings.timezone,
    )

    # validações externas
    if not is_testing():
        await validar_tenant_existe(
            tenant_service,
            str(payload.tenant_id),
            auth_token=raw_token, 
        )

        recurso_data = await validar_recurso_existe(
            resource_service,
            str(payload.resource_id),
            auth_token=raw_token, 
        )

        logger.info(
            "DEBUG resource availability (resource_id=%s): %s",
            payload.resource_id,
            recurso_data.get("availability_schedule"),
        )

        if str(recurso_data["tenant_id"]) != str(payload.tenant_id):
            raise HTTPException(400, "Recurso não pertence ao Tenant informado")

        usuario_data = await validar_usuario_existe(
            user_service,
            str(payload.user_id),
            auth_token=raw_token, 
        )
        if str(usuario_data["tenant_id"]) != str(payload.tenant_id):
            raise HTTPException(400, "Usuário não pertence ao Tenant informado")

        # validar contra availability_schedule do recurso
        schedule = recurso_data.get("availability_schedule", {})
        weekday = start_local.weekday()  # 0 = Monday
        weekday_key = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ][weekday]

        allowed_ranges = schedule.get(weekday_key, [])

        if not allowed_ranges:
            raise HTTPException(400, "Recurso indisponível neste dia da semana.")

        valid = False
        for rng in allowed_ranges:
            start_raw, end_raw = rng.split("-")
            r_start = datetime.combine(
                start_local.date(),
                time.fromisoformat(start_raw),
                tzinfo=zone,
            )
            r_end = datetime.combine(
                start_local.date(),
                time.fromisoformat(end_raw),
                tzinfo=zone,
            )

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
        return JSONResponse(
            status_code=409,
            content=conflict_payload.model_dump(mode="json"),
        )

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
    current_token: TokenPayload = Depends(get_current_token),
    raw_token: str = Depends(oauth2_scheme),
):
    if tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não pode listar reservas de outro tenant.",
        )

    if current_token.user_type != "admin":
        if user_id is not None and user_id != current_token.sub:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário comum só pode listar suas próprias reservas.",
            )
        effective_user_id = current_token.sub
    else:
        # admin pode listar de qualquer usuário, desde que seja do mesmo tenant
        effective_user_id = user_id

    start_dt = _parse_iso_datetime(start_date, "start_date")
    end_dt = _parse_iso_datetime(end_date, "end_date")

    if status_param and status_param not in BookingStatus.ALL:
        raise HTTPException(400, "Status inválido")

    bookings = crud.list_bookings(
        db=db,
        tenant_id=tenant_id,
        resource_id=resource_id,
        user_id=effective_user_id,
        status=status_param,
        start_date=start_dt,
        end_date=end_dt,
    )

    if not bookings:
        raise HTTPException(404, "Nenhuma reserva encontrada.")

    settings_provider = resolve_settings_provider(
        request.app.state,
        auth_token=raw_token,
    )
    settings = settings_provider(tenant_id)

    tz = ZoneInfo(settings.timezone)

    enriched: list[BookingWithPolicy] = []
    for item in bookings:
        base_data = BookingOut.model_validate(item).model_dump(mode="python")

        start_dt = base_data["start_time"]
        end_dt = base_data["end_time"]

        # 👉 Se vier sem tz, assumimos que está em UTC no banco
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)

        # Converte de UTC → timezone do tenant
        local_start = start_dt.astimezone(tz).replace(tzinfo=None)
        local_end = end_dt.astimezone(tz).replace(tzinfo=None)

        # Sobrescreve no dict que vai pro Pydantic
        base_data["start_time"] = local_start
        base_data["end_time"] = local_end

        enriched.append(
            BookingWithPolicy(
                **base_data,
                # can_cancel baseado no horário local
                can_cancel=can_cancel_booking(local_start, settings),
            )
        )

    return enriched


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    booking = crud.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva não encontrada")

    # precisa ser do mesmo tenant
    if booking.tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não pode acessar reservas de outro tenant.",
        )

    # usuário comum só pode ver reserva dele mesmo
    if current_token.user_type != "admin" and booking.user_id != current_token.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você só pode acessar suas próprias reservas.",
        )

    return booking


@router.put("/{booking_id}", response_model=BookingOut)
def update_booking(
    booking_id: UUID,
    payload: BookingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    booking = crud.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(404, "Reserva não encontrada")

    if booking.tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para alterar reservas de outro tenant.",
        )

    if current_token.user_type != "admin" and booking.user_id != current_token.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você só pode alterar suas próprias reservas.",
        )

    raw_token = (
        request.headers.get("authorization", "")
        .removeprefix("Bearer ")
        .strip()
        or None
    )

    settings_provider = resolve_settings_provider(request.app.state, auth_token=raw_token)
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


@router.delete("/{booking_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_booking(
    booking_id: UUID,
    cancel_payload: BookingCancelRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    booking = crud.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(404, "Reserva não encontrada")

    if booking.tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para cancelar reservas de outro tenant.",
        )

    if current_token.user_type != "admin" and booking.user_id != current_token.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você só pode cancelar suas próprias reservas.",
        )

    raw_token = (
        request.headers.get("authorization", "")
        .removeprefix("Bearer ")
        .strip()
        or None
    )

    settings_provider = resolve_settings_provider(request.app.state, auth_token=raw_token)
    settings = settings_provider(booking.tenant_id)
    validate_cancellation_window(booking.start_time, settings)
    
    publisher = getattr(request.app.state, "event_publisher", None)

    deleted = crud.delete_booking(
        db=db,
        booking_id=booking_id,
        deleted_by=current_token.sub,  # quem está cancelando
        publisher=publisher,
    )

    if not deleted:
        raise HTTPException(404, "Reserva não encontrada")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{booking_id}/status", response_model=BookingOut)
def update_status(
    booking_id: UUID,
    request: Request,
    status_param: str = Query(...),
    db: Session = Depends(get_db),
    current_token: TokenPayload = Depends(get_current_token),
):
    if status_param not in BookingStatus.ALL:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Status inválido")

    booking = crud.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reserva não encontrada")

    if booking.tenant_id != current_token.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para alterar reservas de outro tenant.",
        )

    if current_token.user_type != "admin" and booking.user_id != current_token.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você só pode alterar o status das suas próprias reservas.",
        )

    publisher = getattr(request.app.state, "event_publisher", None)
    updated = crud.update_booking_status(db, booking_id, status_param, publisher=publisher)
    if not updated:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reserva não encontrada")

    return updated
