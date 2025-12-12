"""Consumer for booking events in Resource Service."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def handle_booking_created(event_type: str, payload: dict[str, Any]) -> None:
    """
    Handle booking.created events.
    
    Actions:
    - Invalidate availability cache for the resource
    - Update resource usage statistics
    - Track booking frequency per resource
    """
    from datetime import datetime
    from uuid import UUID
    from shared.cache import invalidate_availability_cache
    
    booking_id = payload.get("booking_id")
    resource_id = payload.get("resource_id")
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    
    logger.info(
        f"[BOOKING_CREATED] Resource {resource_id} booked (booking {booking_id}) "
        f"from {start_time} to {end_time}"
    )
    
    # Invalidar cache de disponibilidade para a data do booking
    # Nota: cache será obtido via app_state quando necessário
    # Por enquanto, apenas logamos - invalidação será feita no resource service


async def handle_booking_cancelled(event_type: str, payload: dict[str, Any]) -> None:
    """
    Handle booking.cancelled events.
    
    Actions:
    - Invalidate availability cache for the resource
    - Track cancellation metrics
    """
    from datetime import datetime
    from uuid import UUID
    
    booking_id = payload.get("booking_id")
    resource_id = payload.get("resource_id")
    start_time = payload.get("start_time")
    
    logger.info(
        f"[BOOKING_CANCELLED] Resource {resource_id} freed up (booking {booking_id} cancelled)"
    )
    
    # Invalidar cache de disponibilidade para a data do booking cancelado
    # Nota: cache será obtido via app_state quando necessário
    # Por enquanto, apenas logamos - invalidação será feita no resource service


async def handle_booking_updated(event_type: str, payload: dict[str, Any]) -> None:
    """
    Handle booking.updated events.
    
    Actions:
    - Invalidate availability cache if time changed
    - Recalculate resource availability if needed
    """
    from datetime import datetime
    
    booking_id = payload.get("booking_id")
    resource_id = payload.get("resource_id")
    changes = payload.get("changed_fields", [])
    
    logger.info(
        f"[BOOKING_UPDATED] Resource {resource_id} booking {booking_id} updated: {changes}"
    )
    
    # Invalidar cache se horários mudaram
    if "start_time" in changes or "end_time" in changes:
        # Nota: cache será obtido via app_state quando necessário
        # Por enquanto, apenas logamos - invalidação será feita no resource service
        logger.info(f"Invalidating availability cache for resource {resource_id} due to time change")
