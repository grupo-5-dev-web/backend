from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app.models.booking import Booking, BookingEvent, BookingStatus
from app.schemas.booking_schema import BookingCreate, BookingUpdate
from shared import EventPublisher


def _conflict_query(
    db: Session,
    tenant_id: UUID,
    resource_id: UUID,
    start_time: datetime,
    end_time: datetime,
    ignore_booking_id: Optional[UUID] = None,
):
    query = (
        db.query(Booking)
        .filter(Booking.tenant_id == tenant_id)
        .filter(Booking.resource_id == resource_id)
        .filter(Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]))
        .filter(Booking.end_time > start_time)
        .filter(Booking.start_time < end_time)
    )
    if ignore_booking_id:
        query = query.filter(Booking.id != ignore_booking_id)
    return query


def find_conflicts(
    db: Session,
    tenant_id: UUID,
    resource_id: UUID,
    start_time: datetime,
    end_time: datetime,
    ignore_booking_id: Optional[UUID] = None,
) -> List[Booking]:
    return _conflict_query(db, tenant_id, resource_id, start_time, end_time, ignore_booking_id).all()


def _publish_event(
    publisher: Optional[EventPublisher],
    event_type: str,
    payload: dict,
    *,
    tenant_id: UUID,
) -> None:
    if not publisher:
        return
    publisher.publish(
        event_type,
        payload,
        metadata={"tenant_id": str(tenant_id)},
    )


def create_booking(
    db: Session,
    payload: BookingCreate,
    publisher: Optional[EventPublisher] = None,
) -> Booking:
    booking = Booking(
        tenant_id=payload.tenant_id,
        resource_id=payload.resource_id,
        user_id=payload.user_id,
        client_id=payload.client_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status=payload.status or BookingStatus.CONFIRMED,
        notes=payload.notes,
        recurring_enabled=payload.recurring_enabled,
        recurring_pattern=payload.recurring_pattern.model_dump() if payload.recurring_pattern else None,
    )
    db.add(booking)
    db.flush()

    event = BookingEvent(
        booking_id=booking.id,
        tenant_id=booking.tenant_id,
        event_type="booking.created",
        payload={
            "booking_id": str(booking.id),
            "status": booking.status,
            "start_time": booking.start_time.isoformat(),
            "end_time": booking.end_time.isoformat(),
        },
    )
    db.add(event)
    db.commit()
    db.refresh(booking)

    _publish_event(
        publisher,
        "booking.created",
        {
            "booking_id": str(booking.id),
            "status": booking.status,
            "start_time": booking.start_time.isoformat(),
            "end_time": booking.end_time.isoformat(),
        },
        tenant_id=booking.tenant_id,
    )
    return booking


def list_bookings(
    db: Session,
    tenant_id: UUID,
    resource_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    query = db.query(Booking).filter(Booking.tenant_id == tenant_id)
    if resource_id:
        query = query.filter(Booking.resource_id == resource_id)
    if user_id:
        query = query.filter(Booking.user_id == user_id)
    if status:
        query = query.filter(Booking.status == status)
    if start_date and end_date:
        query = query.filter(
            or_(
                and_(Booking.start_time >= start_date, Booking.start_time < end_date),
                and_(Booking.end_time > start_date, Booking.end_time <= end_date),
            )
        )
    return query.order_by(Booking.start_time.asc()).all()


def get_booking(db: Session, booking_id: UUID) -> Optional[Booking]:
    return db.query(Booking).filter(Booking.id == booking_id).first()


def update_booking(
    db: Session,
    booking_id: UUID,
    payload: BookingUpdate,
    publisher: Optional[EventPublisher] = None,
) -> Optional[Booking]:
    booking = get_booking(db, booking_id)
    if not booking:
        return None

    update_data = payload.model_dump(exclude_unset=True)

    if "recurring_pattern" in update_data and update_data["recurring_pattern"] is not None:
        update_data["recurring_pattern"] = update_data["recurring_pattern"].model_dump()

    for field, value in update_data.items():
        setattr(booking, field, value)

    event = BookingEvent(
        booking_id=booking.id,
        tenant_id=booking.tenant_id,
        event_type="booking.updated",
        payload={"changed_fields": list(update_data.keys())},
    )
    db.add(event)

    db.commit()
    db.refresh(booking)

    _publish_event(
        publisher,
        "booking.updated",
        {
            "booking_id": str(booking.id),
            "changes": list(update_data.keys()),
        },
        tenant_id=booking.tenant_id,
    )
    return booking


def cancel_booking(
    db: Session,
    booking_id: UUID,
    cancelled_by: UUID,
    reason: Optional[str],
    publisher: Optional[EventPublisher] = None,
) -> Optional[Booking]:
    booking = get_booking(db, booking_id)
    if not booking:
        return None

    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = datetime.now(timezone.utc)
    booking.cancelled_by = cancelled_by
    booking.cancellation_reason = reason

    event = BookingEvent(
        booking_id=booking.id,
        tenant_id=booking.tenant_id,
        event_type="booking.cancelled",
        payload={"reason": reason, "cancelled_by": str(cancelled_by)},
    )
    db.add(event)

    db.commit()
    db.refresh(booking)

    _publish_event(
        publisher,
        "booking.cancelled",
        {
            "booking_id": str(booking.id),
            "cancelled_by": str(cancelled_by),
            "reason": reason,
        },
        tenant_id=booking.tenant_id,
    )
    return booking


def update_booking_status(
    db: Session,
    booking_id: UUID,
    status: str,
    publisher: Optional[EventPublisher] = None,
) -> Optional[Booking]:
    booking = get_booking(db, booking_id)
    if not booking:
        return None

    booking.status = status

    event = BookingEvent(
        booking_id=booking.id,
        tenant_id=booking.tenant_id,
        event_type="booking.status_changed",
        payload={"status": status},
    )
    db.add(event)

    db.commit()
    db.refresh(booking)

    _publish_event(
        publisher,
        "booking.status_changed",
        {
            "booking_id": str(booking.id),
            "status": status,
        },
        tenant_id=booking.tenant_id,
    )
    return booking