"""Tests for the EventConsumer class and related utilities."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest

from shared.event_consumer import EventConsumer, cleanup_consumer


class TestEventConsumer:
    """Tests for the EventConsumer class."""
    
    @pytest.fixture
    def consumer(self):
        """Create a basic EventConsumer instance for testing."""
        return EventConsumer(
            redis_url="redis://localhost:6379",
            stream_name="test-events",
            group_name="test-group",
            consumer_name="test-worker-1",
        )
    
    def test_register_handler(self, consumer):
        """Test that handlers can be registered for event types."""
        async def handler(event_type: str, payload: dict[str, Any]) -> None:
            pass
        
        consumer.register_handler("test.event", handler)
        
        assert "test.event" in consumer._handlers
        assert consumer._handlers["test.event"] == handler
    
    def test_register_multiple_handlers(self, consumer):
        """Test that multiple handlers can be registered for different events."""
        async def handler1(event_type: str, payload: dict[str, Any]) -> None:
            pass
        
        async def handler2(event_type: str, payload: dict[str, Any]) -> None:
            pass
        
        consumer.register_handler("event.type1", handler1)
        consumer.register_handler("event.type2", handler2)
        
        assert len(consumer._handlers) == 2
        assert consumer._handlers["event.type1"] == handler1
        assert consumer._handlers["event.type2"] == handler2
    
    def test_initial_state(self, consumer):
        """Test the initial state of a newly created consumer."""
        assert consumer._running is False
        assert consumer._client is None
        assert consumer._handlers == {}
        assert consumer._stream_name == "test-events"
        assert consumer._group_name == "test-group"
        assert consumer._consumer_name == "test-worker-1"
    
    @pytest.mark.asyncio
    async def test_stop_sets_running_to_false(self, consumer):
        """Test that stop() sets _running to False."""
        consumer._running = True
        await consumer.stop()
        assert consumer._running is False
    
    @pytest.mark.asyncio
    async def test_start_returns_early_if_already_running(self, consumer):
        """Test that start() returns early if consumer is already running."""
        consumer._running = True
        
        # If start() doesn't return early, it would try to create a Redis client
        # and fail (since we don't have a real Redis instance)
        with patch.object(consumer, '_client', None):
            # This should return immediately without error
            await consumer.start()
            # Client should still be None since we returned early
            assert consumer._client is None


class TestProcessMessage:
    """Tests for message processing functionality."""
    
    @pytest.fixture
    def consumer_with_mock_redis(self):
        """Create a consumer with mocked Redis client."""
        consumer = EventConsumer(
            redis_url="redis://localhost:6379",
            stream_name="test-events",
            group_name="test-group",
            consumer_name="test-worker-1",
        )
        consumer._client = AsyncMock()
        return consumer
    
    @pytest.mark.asyncio
    async def test_process_message_with_handler(self, consumer_with_mock_redis):
        """Test that messages with registered handlers are processed and acknowledged."""
        consumer = consumer_with_mock_redis
        
        # Track handler calls
        handler_calls = []
        
        async def test_handler(event_type: str, payload: dict[str, Any]) -> None:
            handler_calls.append((event_type, payload))
        
        consumer.register_handler("booking.created", test_handler)
        
        # Create test message
        message_id = b"1234567890-0"
        data = {
            b"event_type": b"booking.created",
            b"payload": b'{"booking_id": "123", "user_id": "456"}',
        }
        
        await consumer._process_message(message_id, data)
        
        # Handler should have been called
        assert len(handler_calls) == 1
        assert handler_calls[0][0] == "booking.created"
        assert handler_calls[0][1] == {"booking_id": "123", "user_id": "456"}
        
        # Message should have been acknowledged
        consumer._client.xack.assert_called_once_with(
            "test-events",
            "test-group",
            message_id,
        )
    
    @pytest.mark.asyncio
    async def test_process_message_without_handler(self, consumer_with_mock_redis):
        """Test that messages without handlers are acknowledged to prevent infinite pending queue."""
        consumer = consumer_with_mock_redis
        
        # No handler registered for this event type
        message_id = b"1234567890-0"
        data = {
            b"event_type": b"unknown.event",
            b"payload": b'{"data": "test"}',
        }
        
        await consumer._process_message(message_id, data)
        
        # Message should still be acknowledged (to prevent infinite pending queue)
        consumer._client.xack.assert_called_once_with(
            "test-events",
            "test-group",
            message_id,
        )
    
    @pytest.mark.asyncio
    async def test_process_message_handles_utf8_message_id(self, consumer_with_mock_redis):
        """Test that UTF-8 message IDs are decoded correctly."""
        consumer = consumer_with_mock_redis
        
        handler_called = False
        
        async def test_handler(event_type: str, payload: dict[str, Any]) -> None:
            nonlocal handler_called
            handler_called = True
        
        consumer.register_handler("test.event", test_handler)
        
        # Standard UTF-8 message ID
        message_id = b"1234567890-0"
        data = {
            b"event_type": b"test.event",
            b"payload": b'{}',
        }
        
        await consumer._process_message(message_id, data)
        
        assert handler_called
    
    @pytest.mark.asyncio
    async def test_process_message_handles_handler_exception(self, consumer_with_mock_redis):
        """Test that handler exceptions are caught and logged without crashing."""
        consumer = consumer_with_mock_redis
        
        async def failing_handler(event_type: str, payload: dict[str, Any]) -> None:
            raise ValueError("Handler failed")
        
        consumer.register_handler("test.event", failing_handler)
        
        message_id = b"1234567890-0"
        data = {
            b"event_type": b"test.event",
            b"payload": b'{}',
        }
        
        # Should not raise
        await consumer._process_message(message_id, data)
        
        # Message should NOT be acknowledged on handler failure (for retry)
        consumer._client.xack.assert_not_called()


class TestCleanupConsumer:
    """Tests for the cleanup_consumer helper function."""
    
    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock(spec=logging.Logger)
    
    @pytest.mark.asyncio
    async def test_cleanup_with_none_consumer(self, mock_logger):
        """Test cleanup when consumer is None."""
        # Should not raise
        await cleanup_consumer(None, None, mock_logger)
    
    @pytest.mark.asyncio
    async def test_cleanup_stops_consumer(self, mock_logger):
        """Test that cleanup stops the consumer."""
        mock_consumer = AsyncMock()
        mock_task = MagicMock()
        mock_task.done.return_value = True
        
        await cleanup_consumer(mock_consumer, mock_task, mock_logger)
        
        mock_consumer.stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_handles_stop_error(self, mock_logger):
        """Test that cleanup handles errors when stopping consumer."""
        mock_consumer = AsyncMock()
        mock_consumer.stop.side_effect = Exception("Stop failed")
        mock_task = MagicMock()
        mock_task.done.return_value = True
        
        # Should not raise
        await cleanup_consumer(mock_consumer, mock_task, mock_logger)
        
        # Should log the warning
        mock_logger.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_cleanup_waits_for_task(self, mock_logger):
        """Test that cleanup waits for task to complete."""
        mock_consumer = AsyncMock()
        mock_task = AsyncMock()
        mock_task.done.return_value = False
        
        await cleanup_consumer(mock_consumer, mock_task, mock_logger, timeout=0.1)
        
        mock_consumer.stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_cancels_task_on_timeout(self, mock_logger):
        """Test that cleanup cancels task if it doesn't stop in time."""
        mock_consumer = AsyncMock()
        
        # Create a real task that won't complete
        async def never_complete():
            await asyncio.sleep(100)
        
        task = asyncio.create_task(never_complete())
        
        # Should cancel the task
        await cleanup_consumer(mock_consumer, task, mock_logger, timeout=0.1)
        
        # Task should be cancelled
        assert task.cancelled() or task.done()
    
    @pytest.mark.asyncio
    async def test_cleanup_task_without_consumer(self, mock_logger):
        """Test that cleanup handles task even when consumer is None."""
        # Create a real task that won't complete
        async def never_complete():
            await asyncio.sleep(100)
        
        task = asyncio.create_task(never_complete())
        
        # Should cancel the task even without a consumer
        await cleanup_consumer(None, task, mock_logger, timeout=0.1)
        
        # Task should be cancelled
        assert task.cancelled() or task.done()
