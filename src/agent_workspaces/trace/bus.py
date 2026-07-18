"""In-process pub/sub for streaming trace events to WebSocket clients.

Every recorded `TraceEvent` is published here; the WebSocket handler subscribes
per `trace_id`. Subscribing atomically snapshots the events already recorded for
that trace AND registers a live queue, so a client that connects mid-run sees the
full history and then every subsequent event with no gap and no duplicates.

This is a single-process implementation. For a multi-worker deployment, back the
bus with Redis pub/sub or Postgres LISTEN/NOTIFY so events fan out across workers.
"""

from __future__ import annotations

import asyncio

from ..models import TraceEvent, TraceId


class TraceBus:
    def __init__(self, max_queue: int = 2000) -> None:
        self._history: dict[TraceId, list[TraceEvent]] = {}
        self._subscribers: dict[TraceId, set[asyncio.Queue[TraceEvent]]] = {}
        self._lock = asyncio.Lock()
        self._max_queue = max_queue

    async def publish(self, event: TraceEvent) -> None:
        async with self._lock:
            self._history.setdefault(event.trace_id, []).append(event)
            subscribers = list(self._subscribers.get(event.trace_id, ()))
        # Fan out outside the lock. Queues are bounded so a slow/stuck client can't
        # grow memory without limit; on overflow we drop the OLDEST event for that
        # client (it can always recover full history by reconnecting).
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass

    async def subscribe(
        self, trace_id: TraceId
    ) -> tuple[list[TraceEvent], asyncio.Queue[TraceEvent]]:
        """Return (history_so_far, live_queue). Both captured under one lock so no
        event can slip between the snapshot and the subscription."""
        queue: asyncio.Queue[TraceEvent] = asyncio.Queue(maxsize=self._max_queue)
        async with self._lock:
            history = list(self._history.get(trace_id, []))
            self._subscribers.setdefault(trace_id, set()).add(queue)
        return history, queue

    async def unsubscribe(self, trace_id: TraceId, queue: asyncio.Queue[TraceEvent]) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(trace_id)
            if subscribers:
                subscribers.discard(queue)
                if not subscribers:
                    del self._subscribers[trace_id]
