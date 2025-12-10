"""Tests for the resource service booking event handlers."""

import pytest

from app.consumers.booking_consumer import (
    handle_booking_cancelled,
    handle_booking_created,
    handle_booking_updated,
)


class TestResourceServiceBookingHandlers:
    """Tests for the resource service booking event handlers."""
    
    @pytest.mark.anyio
    async def test_handle_booking_created(self):
        """Test the resource service booking created handler."""
        payload = {
            "booking_id": "booking-123",
            "resource_id": "resource-789",
            "start_time": "2024-01-01T10:00:00",
            "end_time": "2024-01-01T11:00:00",
        }
        
        # Should not raise
        await handle_booking_created("booking.created", payload)
    
    @pytest.mark.anyio
    async def test_handle_booking_cancelled(self):
        """Test the resource service booking cancelled handler."""
        payload = {
            "booking_id": "booking-123",
            "resource_id": "resource-789",
        }
        
        # Should not raise
        await handle_booking_cancelled("booking.cancelled", payload)
    
    @pytest.mark.anyio
    async def test_handle_booking_updated(self):
        """Test the resource service booking updated handler."""
        payload = {
            "booking_id": "booking-123",
            "resource_id": "resource-789",
            "changes": {"start_time": "2024-01-01T11:00:00"},
        }
        
        # Should not raise
        await handle_booking_updated("booking.updated", payload)
