"""Generic event consumer for Redis Streams with consumer groups."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


EventHandler = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]


class EventConsumer:
    """
    Consume events from Redis Streams using consumer groups.
    
    Example:
        consumer = EventConsumer(
            redis_url="redis://localhost:6379",
            stream_name="booking-events",
            group_name="notification-service",
            consumer_name="worker-1"
        )
        
        async def handle_booking_created(event_type: str, payload: dict):
            print(f"Handling {event_type}: {payload}")
        
        consumer.register_handler("booking.created", handle_booking_created)
        await consumer.start()
    """

    def __init__(
        self,
        redis_url: str,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        *,
        block_ms: int = 5000,
        count: int = 10,
    ) -> None:
        """
        Initialize event consumer.
        
        Args:
            redis_url: Redis connection URL
            stream_name: Name of the Redis Stream to consume
            group_name: Consumer group name (all workers in same group share load)
            consumer_name: Unique name for this consumer instance
            block_ms: Time to block waiting for new messages (milliseconds)
            count: Maximum number of messages to read per batch
        """
        self._redis_url = redis_url
        self._stream_name = stream_name
        self._group_name = group_name
        self._consumer_name = consumer_name
        self._block_ms = block_ms
        self._count = count
        self._handlers: dict[str, EventHandler] = {}
        self._client: Optional[aioredis.Redis] = None
        self._running = False

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for a specific event type."""
        self._handlers[event_type] = handler
        logger.info(f"Registered handler for event type: {event_type}")

    async def _ensure_consumer_group(self) -> None:
        """Create consumer group if it doesn't exist."""
        try:
            await self._client.xgroup_create(
                name=self._stream_name,
                groupname=self._group_name,
                id="0",
                mkstream=True,
            )
            logger.info(
                f"Created consumer group '{self._group_name}' for stream '{self._stream_name}'"
            )
        except aioredis.ResponseError as e:
            # Group already exists
            if "BUSYGROUP" not in str(e):
                raise

    async def _process_message(self, message_id: bytes, data: dict[bytes, bytes]) -> None:
        """Process a single message from the stream."""
        try:
            # Decode message
            event_type = data.get(b"event_type", b"").decode("utf-8")
            payload_str = data.get(b"payload", b"{}").decode("utf-8")
            
            # Parse payload
            import json
            payload = json.loads(payload_str)
            
            # Find and execute handler
            handler = self._handlers.get(event_type)
            if handler:
                logger.debug(f"Processing {event_type}: {message_id.decode()}")
                await handler(event_type, payload)
            else:
                logger.debug(f"No handler for event type: {event_type}")
            
            # Acknowledge message
            await self._client.xack(
                self._stream_name,
                self._group_name,
                message_id,
            )
            
        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}", exc_info=True)
            # Message will be retried by pending entries logic

    async def _read_pending_messages(self) -> None:
        """Read and process messages that were delivered but not acknowledged."""
        try:
            # Get pending messages for this consumer
            pending = await self._client.xpending_range(
                name=self._stream_name,
                groupname=self._group_name,
                min="-",
                max="+",
                count=self._count,
                consumername=self._consumer_name,
            )
            
            if pending:
                logger.info(f"Found {len(pending)} pending messages to process")
                
                for entry in pending:
                    message_id = entry["message_id"]
                    # Read the actual message
                    messages = await self._client.xrange(
                        self._stream_name,
                        min=message_id,
                        max=message_id,
                    )
                    if messages:
                        _, data = messages[0]
                        await self._process_message(message_id, data)
                        
        except Exception as e:
            logger.error(f"Error reading pending messages: {e}", exc_info=True)

    async def start(self) -> None:
        """Start consuming events (blocking call)."""
        if self._running:
            logger.warning("Consumer already running")
            return

        self._running = True
        self._client = aioredis.Redis.from_url(self._redis_url)
        
        try:
            await self._ensure_consumer_group()
            logger.info(
                f"Consumer '{self._consumer_name}' started on stream '{self._stream_name}'"
            )
            
            # Process any pending messages first
            await self._read_pending_messages()
            
            # Main consumption loop
            while self._running:
                try:
                    # Read new messages
                    messages = await self._client.xreadgroup(
                        groupname=self._group_name,
                        consumername=self._consumer_name,
                        streams={self._stream_name: ">"},
                        count=self._count,
                        block=self._block_ms,
                    )
                    
                    if not messages:
                        continue
                    
                    # Process messages
                    for stream_name, stream_messages in messages:
                        for message_id, data in stream_messages:
                            await self._process_message(message_id, data)
                            
                except asyncio.CancelledError:
                    logger.info("Consumer task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in consumer loop: {e}", exc_info=True)
                    await asyncio.sleep(1)  # Backoff on error
                    
        finally:
            self._running = False
            if self._client:
                await self._client.aclose()
            logger.info(f"Consumer '{self._consumer_name}' stopped")

    async def stop(self) -> None:
        """Stop consuming events."""
        self._running = False
        logger.info("Stopping consumer...")
