"""TraceRecorder — open, append to, and finalize an execution trajectory.

The recorder must persist OUTSIDE the sandbox so a destroyed (or compromised)
sandbox can't take its own trace with it. Every event is also published to the
`TraceBus` so live WebSocket clients receive it.
"""

from __future__ import annotations

import abc
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings
from ..models import TraceEvent, TraceId, WorkspaceId, WorkspaceRequest
from .bus import TraceBus


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TraceRecorder(abc.ABC):
    """Records the full trajectory of a workspace run to durable storage."""

    @abc.abstractmethod
    async def start(self, workspace_id: WorkspaceId, request: WorkspaceRequest) -> TraceId:
        """Open a new trace and return its id. Called before the agent runs."""

    @abc.abstractmethod
    async def record(self, event: TraceEvent) -> None:
        """Append one event. Should be cheap and non-blocking on the hot path."""

    @abc.abstractmethod
    async def finalize(self, trace_id: TraceId) -> None:
        """Seal the trace and flush anything buffered. Idempotent."""

    @abc.abstractmethod
    async def load(self, trace_id: TraceId) -> list[TraceEvent]:
        """Read a persisted trace back for replay / evaluation."""


class InMemoryTraceRecorder(TraceRecorder):
    """Keeps traces in a process dict and publishes to the bus. Lost on restart.

    Replace the dict with a durable store (object storage, append-only log,
    Postgres) so traces survive the process. Target: settings.trace_store_uri.
    """

    def __init__(self, settings: Settings, bus: TraceBus | None = None) -> None:
        self.settings = settings
        self.bus = bus
        self._traces: dict[TraceId, list[TraceEvent]] = {}

    async def _emit(self, event: TraceEvent) -> None:
        self._traces.setdefault(event.trace_id, []).append(event)
        if self.bus is not None:
            await self.bus.publish(event)

    async def start(self, workspace_id: WorkspaceId, request: WorkspaceRequest) -> TraceId:
        trace_id: TraceId = f"tr_{uuid.uuid4().hex[:12]}"
        await self._emit(
            TraceEvent(
                trace_id=trace_id,
                ts=_now(),
                kind="workspace.start",
                payload={
                    "workspace_id": workspace_id,
                    "agent_id": request.agent_id,
                    "task_prompt": request.task_prompt,
                },
            )
        )
        return trace_id

    async def record(self, event: TraceEvent) -> None:
        await self._emit(event)

    async def finalize(self, trace_id: TraceId) -> None:
        await self._emit(
            TraceEvent(trace_id=trace_id, ts=_now(), kind="workspace.end", payload={})
        )

    async def load(self, trace_id: TraceId) -> list[TraceEvent]:
        return self._traces.get(trace_id, [])


class JsonlTraceRecorder(InMemoryTraceRecorder):
    """Durable trace store: one append-only JSONL file per trace.

    The whole point of the trace plane is that a sandbox can be *destroyed*
    while its trajectory survives for replay, debugging, and evaluation — an
    in-memory dict dies with the process, which breaks that promise. This
    recorder appends every event to ``{trace_store_uri}/{trace_id}.jsonl``
    (via a worker thread so file I/O never stalls the agent's event loop) and
    falls back to disk on `load`, so traces survive a restart.

    Write durability is fsync-less by design: losing the tail of a trace in a
    hard crash beats applying backpressure to the agent.
    """

    def __init__(self, settings: Settings, bus: TraceBus | None = None) -> None:
        super().__init__(settings, bus=bus)
        uri = settings.trace_store_uri.removeprefix("file://")
        self.store_dir = Path(uri).expanduser()
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, trace_id: TraceId) -> Path:
        # Trace ids are minted internally (tr_<hex>), but never trust a path join.
        safe = trace_id.replace("/", "_").replace("..", "_")
        return self.store_dir / f"{safe}.jsonl"

    async def _emit(self, event: TraceEvent) -> None:
        await super()._emit(event)
        line = event.model_dump_json()
        path = self._path(event.trace_id)

        def _append() -> None:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")

        await asyncio.to_thread(_append)

    async def load(self, trace_id: TraceId) -> list[TraceEvent]:
        events = await super().load(trace_id)
        if events:
            return events
        path = self._path(trace_id)
        if not path.exists():
            return []

        def _read() -> list[TraceEvent]:
            out: list[TraceEvent] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    out.append(TraceEvent(**json.loads(line)))
            return out

        return await asyncio.to_thread(_read)
