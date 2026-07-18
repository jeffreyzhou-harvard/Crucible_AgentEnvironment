"""Orchestrator — composes the four planes into one workspace lifecycle.

This is the spine of the system. It depends only on each plane's *interface*, so
you can start with the in-memory/mock implementations and swap in real backends
without touching this file.

Lifecycle (see also the diagram in README.md):

    provision → branch data → secure → run → trace → recycle/destroy
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .config import Settings, get_settings
from .control.scheduler import Scheduler
from .data.provisioner import DataPlane
from .execution.sandbox import SandboxRuntime
from .models import (
    ExecutionResult,
    Workspace,
    WorkspaceId,
    WorkspaceRequest,
)
from .security.isolation import SecurityPlane
from .trace.recorder import TraceRecorder


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Orchestrator:
    """Wires the planes together. One instance per process is fine.

    Each plane is injected so tests can pass mocks and prod can pass real backends.
    """

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

    async def create_workspace(self, request: WorkspaceRequest) -> Workspace:
        """Assemble a ready-to-run workspace for `request`.

        Order matters: acquire the sandbox, branch data and lock down the network
        BEFORE the agent can touch anything, then hand it over.
        """
        workspace_id: WorkspaceId = f"ws_{uuid.uuid4().hex[:12]}"

        # 1. CONTROL: claim a warm sandbox or provision one on demand.
        sandbox = await self.scheduler.acquire(request)

        # 2. TRACE: open a trajectory before anything happens inside the sandbox.
        trace_id = await self.trace.start(workspace_id=workspace_id, request=request)

        # 3. DATA: branch datasets from the read-only reference snapshot.
        #    TODO: on failure here, we must release the sandbox back to the pool.
        branch_ids = await self.data.branch(sandbox=sandbox, datasets=request.datasets)

        # 4. SECURITY: attach the credential proxy and apply ingress/egress policy
        #    BEFORE the agent runs. Nothing the agent does should precede this.
        await self.security.secure(sandbox=sandbox, request=request)

        # 5. EXECUTION: mount repos + tooling and attach the agent.
        await self.runtime.attach(sandbox=sandbox, request=request)

        return Workspace(
            id=workspace_id,
            request=request,
            sandbox=sandbox,
            trace_id=trace_id,
            data_branch_ids=branch_ids,
            created_at=_now(),
        )

    async def run(self, workspace: Workspace) -> ExecutionResult:
        """Run the agent to completion inside an assembled workspace.

        TODO: enforce `settings.sandbox_max_lifetime_seconds` as a hard timeout and
        stream trace events (self.trace.record) as the agent produces them.
        """
        result = await self.runtime.run_agent(
            sandbox=workspace.sandbox,
            request=workspace.request,
            trace_id=workspace.trace_id,
        )
        return result

    async def destroy_workspace(self, workspace: Workspace) -> None:
        """Tear everything down. Must be idempotent and safe to call after failures.

        The sandbox is destroyed but its trace survives for replay/eval.
        TODO: run these teardown steps even if earlier ones raise (gather + report),
        so a single failure can't leak a sandbox, a data branch, or a proxy route.
        """
        await self.trace.finalize(workspace.trace_id)
        await self.data.teardown(workspace.data_branch_ids)
        await self.security.teardown(workspace.sandbox)
        # CONTROL decides whether to recycle the sandbox into the warm pool or kill it.
        await self.scheduler.release(workspace.sandbox)

    async def execute(self, request: WorkspaceRequest) -> ExecutionResult:
        """Convenience: full create → run → destroy, with guaranteed teardown."""
        workspace = await self.create_workspace(request)
        try:
            return await self.run(workspace)
        finally:
            await self.destroy_workspace(workspace)
