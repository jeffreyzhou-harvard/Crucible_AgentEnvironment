"""SandboxRuntime — the execution plane's public interface.

Responsible for turning a claimed Sandbox handle into a live environment the agent
can work in, running the agent to completion, and tearing the environment down.
"""

from __future__ import annotations

import abc
from datetime import datetime, timezone

from ..config import Settings
from ..models import ExecutionResult, Sandbox, SandboxState, TraceId, WorkspaceRequest
from .filesystem import Filesystem
from .runtime import RuntimeBackend


class SandboxRuntime(abc.ABC):
    """Attaches an agent to a sandbox and runs its task."""

    @abc.abstractmethod
    async def attach(self, sandbox: Sandbox, request: WorkspaceRequest) -> None:
        """Prepare the live environment: mount repos, tooling, MCP servers.

        Called AFTER the security plane has locked the sandbox down.
        """

    @abc.abstractmethod
    async def run_agent(
        self, sandbox: Sandbox, request: WorkspaceRequest, trace_id: TraceId
    ) -> ExecutionResult:
        """Run the agent to completion, streaming trace events as it goes."""

    @abc.abstractmethod
    async def destroy(self, sandbox: Sandbox) -> None:
        """Stop and remove the live environment. Idempotent."""


class MockSandboxRuntime(SandboxRuntime):
    """A no-op runtime that lets the lifecycle run without real infrastructure.

    Replace with a runtime that drives a real RuntimeBackend + Filesystem.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # TODO: construct the concrete backend from settings.runtime_backend
        #       (docker/firecracker/k8s) instead of leaving it None.
        self.backend: RuntimeBackend | None = None
        self.filesystem: Filesystem | None = None

    async def attach(self, sandbox: Sandbox, request: WorkspaceRequest) -> None:
        # TODO: clone request.repos into the writable filesystem, install tooling,
        #       start MCP servers, and confirm Docker-in-sandbox is available.
        sandbox.state = SandboxState.RUNNING

    async def run_agent(
        self, sandbox: Sandbox, request: WorkspaceRequest, trace_id: TraceId
    ) -> ExecutionResult:
        # TODO: hand control to the actual agent runtime. This is where the agent
        #       loop executes commands / tool calls inside the sandbox. Enforce
        #       settings.sandbox_max_lifetime_seconds as a hard wall-clock limit.
        return ExecutionResult(
            workspace_id="",  # filled by the orchestrator's Workspace; TODO thread through
            trace_id=trace_id,
            exit_code=0,
            succeeded=True,
            summary="mock run: no agent executed",
        )

    async def destroy(self, sandbox: Sandbox) -> None:
        sandbox.state = SandboxState.DESTROYED
