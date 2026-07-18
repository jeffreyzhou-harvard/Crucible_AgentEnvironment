"""Orchestrator — composes the four planes into one workspace lifecycle.

This is the spine of the system. It depends only on each plane's *interface*, so
mocks and real backends are interchangeable.

The lifecycle is streaming-first: `begin()` opens the trace and returns ids
immediately (so a client can connect to the stream), then `run_lifecycle()` runs
the whole thing in the background, emitting a trace event as each plane fires:

    control → data → security → execution → agent → teardown

Every step publishes to the trace bus, so the frontend watches the planes light up
and the agent work in real time.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable
from typing import Any

from .config import Settings, get_settings
from .control.scheduler import Scheduler
from .data.provisioner import DataPlane
from .execution.sandbox import SandboxRuntime
from .models import ExecutionResult, Sandbox, TraceId, WorkspaceId, WorkspaceRequest
from .security.isolation import SecurityPlane
from .trace.recorder import TraceRecorder
from .trace.tracer import Tracer


class Orchestrator:
    """Wires the planes together. One instance per process is fine."""

    def __init__(
        self,
        *,
        scheduler: Scheduler,
        runtime: SandboxRuntime,
        security: SecurityPlane,
        data: DataPlane,
        trace: TraceRecorder,
        settings: Settings | None = None,
    ) -> None:
        self.scheduler = scheduler
        self.runtime = runtime
        self.security = security
        self.data = data
        self.trace = trace
        self.settings = settings or get_settings()

    async def begin(self, request: WorkspaceRequest) -> tuple[WorkspaceId, TraceId]:
        """Mint ids and open the trace. Cheap and fast — safe on the request path.

        Returns (workspace_id, trace_id) so the caller can hand the client a stream
        URL before the (slow) lifecycle runs.
        """
        workspace_id: WorkspaceId = f"ws_{uuid.uuid4().hex[:12]}"
        trace_id = await self.trace.start(workspace_id=workspace_id, request=request)
        return workspace_id, trace_id

    async def run_lifecycle(
        self, request: WorkspaceRequest, workspace_id: WorkspaceId, trace_id: TraceId
    ) -> ExecutionResult | None:
        """Assemble → run → tear down, emitting a trace event at every step.

        Ordering is a contract: the security plane must lock the sandbox down BEFORE
        the agent runs; teardown must run even if an earlier step raises so we never
        leak a sandbox, a data branch, a proxy identity, or a firewall rule.
        """
        tracer = Tracer(self.trace, trace_id, workspace_id)
        sandbox: Sandbox | None = None
        branch_ids: list[str] = []
        result: ExecutionResult | None = None

        try:
            # 1. CONTROL: claim a warm sandbox or provision one on demand.
            sandbox = await self.scheduler.acquire(request)
            await tracer.emit(
                "plane.control", sandbox_id=sandbox.id, base_image=sandbox.base_image
            )

            # 2. DATA: branch datasets from the read-only reference snapshot.
            branch_ids = await self.data.branch(sandbox=sandbox, datasets=request.datasets)
            await tracer.emit("plane.data", branch_ids=branch_ids)

            # 3. SECURITY: credential proxy + network policy, BEFORE the agent runs.
            #    Pass the tracer so the plane can stream egress decisions live.
            await self.security.secure(sandbox=sandbox, request=request, tracer=tracer)
            await tracer.emit(
                "plane.security",
                egress=self.settings.egress_hosts + request.extra_egress_hosts,
                credential_proxy=self.settings.credential_proxy_url,
            )

            # 4. EXECUTION: boot the environment, clone repos, attach the agent.
            await self.runtime.attach(sandbox=sandbox, request=request)
            await tracer.emit(
                "plane.execution",
                sandbox_id=sandbox.id,
                repos=[r.url for r in request.repos],
            )

            # 5. Run the agent to completion (streams its own trace events).
            result = await self.runtime.run_agent(
                sandbox=sandbox, request=request, tracer=tracer
            )
            result.workspace_id = workspace_id
        except Exception as exc:  # noqa: BLE001 — surface any failure into the trace
            await tracer.emit("error", message=f"{type(exc).__name__}: {exc}")
        finally:
            # Teardown runs to completion: one step failing must not skip the rest,
            # or we leak a data branch, proxy identity, firewall rule, or sandbox.
            # Each failure is surfaced into the trace; finalize() runs last so
            # `workspace.end` stays the terminal event on the stream.
            async def _safe(step: str, coro: Awaitable[Any]) -> None:
                try:
                    await coro
                except Exception as exc:  # noqa: BLE001 — a leak is an incident, not a crash
                    await tracer.emit("error", message=f"teardown[{step}]: {type(exc).__name__}: {exc}")

            if branch_ids:
                await _safe("data", self.data.teardown(branch_ids))
            if sandbox is not None:
                await _safe("security", self.security.teardown(sandbox, tracer=tracer))
                await _safe("runtime", self.runtime.destroy(sandbox))
                await _safe("scheduler", self.scheduler.release(sandbox))
            await self.trace.finalize(trace_id)

        return result

    async def execute(self, request: WorkspaceRequest) -> ExecutionResult | None:
        """Convenience: full begin → run → teardown, awaited to completion.

        Used by tests and any non-streaming caller. The streaming API instead calls
        `begin()` then schedules `run_lifecycle()` in the background.
        """
        workspace_id, trace_id = await self.begin(request)
        return await self.run_lifecycle(request, workspace_id, trace_id)
