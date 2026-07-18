"""Tracer — a thin, bound emit-helper handed to whatever is doing work.

The orchestrator and the agent loop don't hold a `TraceRecorder` and a trace id
separately; they hold a `Tracer` that knows both and turns
`await tracer.emit("tool_call", command=...)` into a persisted + published
`TraceEvent`. Keeps trace plumbing out of the plane code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models import TraceEvent, TraceId, WorkspaceId
from .recorder import TraceRecorder


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Tracer:
    def __init__(
        self,
        recorder: TraceRecorder,
        trace_id: TraceId,
        workspace_id: WorkspaceId,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.recorder = recorder
        self.trace_id = trace_id
        self.workspace_id = workspace_id
        # Merged into every event payload — e.g. {"candidate": 2} so a fan-out of
        # candidates can share one trace stream and the frontend can demux by column.
        self.context = context or {}

    async def emit(self, kind: str, **payload: Any) -> None:
        await self.recorder.record(
            TraceEvent(
                trace_id=self.trace_id,
                ts=_now(),
                kind=kind,
                payload={**self.context, **payload},
            )
        )
