"""Consumer for booking events in Resource Service."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def handle_booking_created(event_type: str, payload: dict[str, Any]) -> None:
    """
    Handle booking.created events.
    
    Actions:
    - Update resource usage statistics
    - Track booking frequency per resource
    """
    booking_id = payload.get("booking_id")
    resource_id = payload.get("resource_id")
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    
    logger.info(
        f"[BOOKING_CREATED] Resource {resource_id} booked (booking {booking_id}) "
        f"from {start_time} to {end_time}"
    )
    
    # TODO: Update resource metrics
    # await update_resource_usage_stats(resource_id, start_time, end_time)


async def handle_booking_cancelled(event_type: str, payload: dict[str, Any]) -> None:
    """
    Handle booking.cancelled events.
    
    Actions:
    - Update resource availability cache if needed
    - Track cancellation metrics
    """
    booking_id = payload.get("booking_id")
    resource_id = payload.get("resource_id")
    
    logger.info(
        f"[BOOKING_CANCELLED] Resource {resource_id} freed up (booking {booking_id} cancelled)"
    )
    
    # TODO: Invalidate availability cache for this resource
    # await invalidate_resource_cache(resource_id)


async def handle_booking_updated(event_type: str, payload: dict[str, Any]) -> None:
    """
    Handle booking.updated events.
    
    Actions:
    - Recalculate resource availability if time changed
    """
    booking_id = payload.get("booking_id")
    resource_id = payload.get("resource_id")
    changes = payload.get("changes", {})
    
    logger.info(
        f"[BOOKING_UPDATED] Resource {resource_id} booking {booking_id} updated: {changes}"
    )
    
    # TODO: Handle time changes
    # if "start_time" in changes or "end_time" in changes:
    #     await recalculate_availability(resource_id)
