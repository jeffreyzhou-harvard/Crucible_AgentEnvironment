"""SandboxRuntime — the execution plane's public interface.

Turns a claimed Sandbox handle into a live environment, runs the agent to
completion, and tears the environment down.
"""

from __future__ import annotations

import abc

from ..config import Settings
from ..models import ExecutionResult, Sandbox, SandboxState, WorkspaceRequest
from ..trace.tracer import Tracer


class SandboxRuntime(abc.ABC):
    """Attaches an agent to a sandbox and runs its task."""

    @abc.abstractmethod
    async def attach(self, sandbox: Sandbox, request: WorkspaceRequest) -> None:
        """Prepare the live environment: boot it, clone repos, install tooling.

        Called AFTER the security plane has locked the sandbox down.
        """

    @abc.abstractmethod
    async def run_agent(
        self, sandbox: Sandbox, request: WorkspaceRequest, tracer: Tracer
    ) -> ExecutionResult:
        """Run the agent to completion, emitting trace events via `tracer`."""

    @abc.abstractmethod
    async def destroy(self, sandbox: Sandbox) -> None:
        """Stop and remove the live environment. Idempotent."""


class MockSandboxRuntime(SandboxRuntime):
    """A no-op runtime that lets the lifecycle run without real infrastructure.

    It emits a couple of trace events so the streaming path and the frontend can
    be exercised end-to-end with no Docker daemon and no API key.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def attach(self, sandbox: Sandbox, request: WorkspaceRequest) -> None:
        sandbox.runtime_ref = f"mock://{sandbox.id}"
        sandbox.state = SandboxState.RUNNING

    async def run_agent(
        self, sandbox: Sandbox, request: WorkspaceRequest, tracer: Tracer
    ) -> ExecutionResult:
        await tracer.emit("agent.start", model="mock")
        await tracer.emit("agent.message", text=f"(mock) received task: {request.task_prompt}")
        await tracer.emit("tool_call", command="echo 'mock sandbox — no agent ran'")
        await tracer.emit("command_output", exit_code=0, output="mock sandbox — no agent ran")
        await tracer.emit("agent.done", succeeded=True, stop_reason="end_turn")
        return ExecutionResult(
            workspace_id="",
            trace_id=tracer.trace_id,
            exit_code=0,
            succeeded=True,
            summary="mock run: no agent executed",
        )

    async def destroy(self, sandbox: Sandbox) -> None:
        sandbox.state = SandboxState.DESTROYED


class DockerSandboxRuntime(SandboxRuntime):
    """Real execution plane: a Docker container per sandbox + the Claude agent loop."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        from .agent import ClaudeAgent
        from .runtime import DockerBackend

        self.backend = DockerBackend(settings)
        self.agent = ClaudeAgent(settings, self.backend)

    async def attach(self, sandbox: Sandbox, request: WorkspaceRequest) -> None:
        sandbox.runtime_ref = await self.backend.restore_from_snapshot(sandbox.base_image)
        sandbox.state = SandboxState.RUNNING

        # Clone requested repos into the workdir. Public repos only for now.
        # TODO: private-repo auth must come from the credential proxy, never a token
        #       injected into the container (security plane).
        for repo in request.repos:
            name = repo.url.rstrip("/").split("/")[-1].removesuffix(".git")
            dest = f"{self.settings.sandbox_workdir}/{name}"
            await self.backend.exec(
                sandbox.runtime_ref,
                ["git", "clone", "--depth", "1", "--branch", repo.ref, repo.url, dest],
            )

    async def run_agent(
        self, sandbox: Sandbox, request: WorkspaceRequest, tracer: Tracer
    ) -> ExecutionResult:
        assert sandbox.runtime_ref is not None, "attach() must run before run_agent()"
        return await self.agent.run(sandbox.runtime_ref, request, tracer)

    async def destroy(self, sandbox: Sandbox) -> None:
        if sandbox.runtime_ref:
            await self.backend.destroy(sandbox.runtime_ref)
        sandbox.state = SandboxState.DESTROYED
