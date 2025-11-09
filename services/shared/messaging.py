"""Simple event publisher abstraction backed by Redis Streams."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import redis

logger = logging.getLogger(__name__)


class EventPublisher:
    """Publish domain events to a Redis Stream.

    The implementation is intentionally lightweight; callers can build higher-level
    abstractions (retry, tracing, etc.) on top of it.
    """

    def __init__(self, redis_url: str, stream_name: str, *, maxlen: Optional[int] = 1000) -> None:
        self._stream_name = stream_name
        self._maxlen = maxlen
        self._client = redis.Redis.from_url(redis_url)

    def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send an event to the configured stream.

        Parameters
        ----------
        event_type:
            Canonical name, e.g. ``booking.created``.
        payload:
            Serialisable body (will be JSON dumped).
        metadata:
            Optional envelope metadata (correlation, tenant id, etc.).
        """

        event = {
            "event_type": event_type,
            "payload": json.dumps(payload, default=str),
        }
        if metadata:
            event["metadata"] = json.dumps(metadata, default=str)

        try:
            self._client.xadd(
                self._stream_name,
                event,
                maxlen=self._maxlen,
                approximate=True if self._maxlen else False,
            )
        except Exception:  # pragma: no cover - log and continue
            logger.exception("Failed to publish event '%s' to stream '%s'", event_type, self._stream_name)
