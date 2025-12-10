"""Tests for the user service booking event handlers."""

import pytest

from app.consumers.booking_consumer import (
    handle_booking_cancelled,
    handle_booking_created,
    handle_booking_status_changed,
)


class TestUserServiceBookingHandlers:
    """Tests for the user service booking event handlers."""
    
    @pytest.mark.anyio
    async def test_handle_booking_created(self):
        """Test the user service booking created handler."""
        payload = {
            "booking_id": "booking-123",
            "user_id": "user-456",
            "resource_id": "resource-789",
            "start_time": "2024-01-01T10:00:00",
        }
        
        # Should not raise
        await handle_booking_created("booking.created", payload)
    
    @pytest.mark.anyio
    async def test_handle_booking_cancelled(self):
        """Test the user service booking cancelled handler."""
        payload = {
            "booking_id": "booking-123",
            "cancelled_by": "user-456",
            "reason": "User requested cancellation",
        }
        
        # Should not raise
        await handle_booking_cancelled("booking.cancelled", payload)
    
    @pytest.mark.anyio
    async def test_handle_booking_status_changed(self):
        """Test the user service booking status changed handler."""
        payload = {
            "booking_id": "booking-123",
            "old_status": "pending",
            "new_status": "confirmed",
        }
        
        # Should not raise
        await handle_booking_status_changed("booking.status_changed", payload)
