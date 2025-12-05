"""Initialize consumers package."""

from .booking_consumer import (
    handle_booking_created,
    handle_booking_cancelled,
    handle_booking_status_changed,
)

__all__ = [
    "handle_booking_created",
    "handle_booking_cancelled",
    "handle_booking_status_changed",
]
