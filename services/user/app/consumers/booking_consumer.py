"""Consumer for booking events in User Service."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def handle_booking_created(event_type: str, payload: dict[str, Any]) -> None:
    """
    Handle booking.created events.
    
    Actions:
    - Log booking creation for the user
    - Future: Send email/push notification to user
    """
    booking_id = payload.get("booking_id")
    user_id = payload.get("user_id")
    resource_id = payload.get("resource_id")
    start_time = payload.get("start_time")
    
    logger.info(
        f"[BOOKING_CREATED] User {user_id} created booking {booking_id} "
        f"for resource {resource_id} at {start_time}"
    )
    
    # TODO: Send notification to user
    # await send_email_notification(user_id, "Reserva confirmada", ...)
    # await send_push_notification(user_id, "Sua reserva foi confirmada")


async def handle_booking_cancelled(event_type: str, payload: dict[str, Any]) -> None:
    """
    Handle booking.cancelled events.
    
    Actions:
    - Log cancellation
    - Future: Send cancellation notification to user
    """
    booking_id = payload.get("booking_id")
    cancelled_by = payload.get("cancelled_by")
    reason = payload.get("reason", "Não informado")
    
    logger.info(
        f"[BOOKING_CANCELLED] Booking {booking_id} cancelled by {cancelled_by}. "
        f"Reason: {reason}"
    )
    
    # TODO: Notify user about cancellation
    # await send_email_notification(user_id, "Reserva cancelada", ...)


async def handle_booking_status_changed(event_type: str, payload: dict[str, Any]) -> None:
    """
    Handle booking.status_changed events.
    
    Actions:
    - Log status changes
    - Notify user if status changed to rejected/cancelled_by_system
    """
    booking_id = payload.get("booking_id")
    old_status = payload.get("old_status")
    new_status = payload.get("new_status")
    
    logger.info(
        f"[BOOKING_STATUS_CHANGED] Booking {booking_id}: {old_status} -> {new_status}"
    )
    
    # TODO: Conditional notifications based on status
    # if new_status == "rejected":
    #     await send_notification(user_id, "Reserva rejeitada")
