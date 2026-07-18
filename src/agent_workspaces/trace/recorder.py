"""TraceRecorder — open, append to, and finalize an execution trajectory.

The recorder must persist OUTSIDE the sandbox so a destroyed (or compromised)
sandbox can't take its own trace with it.
"""

from __future__ import annotations

import abc
import uuid
from datetime import datetime, timezone

from ..config import Settings
from ..models import TraceEvent, TraceId, WorkspaceId, WorkspaceRequest


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TraceRecorder(abc.ABC):
    """Records the full trajectory of a workspace run to durable storage."""

    @abc.abstractmethod
    async def start(self, workspace_id: WorkspaceId, request: WorkspaceRequest) -> TraceId:
        """Open a new trace and return its id. Called before the agent runs."""

    @abc.abstractmethod
    async def record(self, event: TraceEvent) -> None:
        """Append one event. Should be cheap and non-blocking on the hot path.

        TODO: buffer + flush asynchronously; never let trace writes stall the agent.
        Decide the durability bar — a lost tail of events vs. backpressure.
        """

    @abc.abstractmethod
    async def finalize(self, trace_id: TraceId) -> None:
        """Seal the trace and flush anything buffered. Idempotent."""

    @abc.abstractmethod
    async def load(self, trace_id: TraceId) -> list[TraceEvent]:
        """Read a persisted trace back for replay / evaluation."""


class InMemoryTraceRecorder(TraceRecorder):
    """Keeps traces in a process dict. Fine for tests; lost on restart.

    Replace with a durable store (object storage, append-only log, Postgres) so
    traces survive the sandbox — and the process. Target: settings.trace_store_uri.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._traces: dict[TraceId, list[TraceEvent]] = {}

    async def start(self, workspace_id: WorkspaceId, request: WorkspaceRequest) -> TraceId:
        trace_id: TraceId = f"tr_{uuid.uuid4().hex[:12]}"
        self._traces[trace_id] = [
            TraceEvent(
                trace_id=trace_id,
                ts=_now(),
                kind="workspace.start",
                payload={"workspace_id": workspace_id, "agent_id": request.agent_id},
            )
        ]
        return trace_id

    async def record(self, event: TraceEvent) -> None:
        self._traces.setdefault(event.trace_id, []).append(event)

    async def finalize(self, trace_id: TraceId) -> None:
        self._traces.setdefault(trace_id, []).append(
            TraceEvent(trace_id=trace_id, ts=_now(), kind="workspace.end", payload={})
        )
        # TODO: flush to settings.trace_store_uri here so the trace outlives the process.

    async def load(self, trace_id: TraceId) -> list[TraceEvent]:
        return self._traces.get(trace_id, [])
