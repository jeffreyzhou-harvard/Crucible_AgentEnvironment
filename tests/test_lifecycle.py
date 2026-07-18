"""End-to-end lifecycle tests against the mock planes.

These pass today with the scaffold's mocks. They double as executable documentation
of the contract each plane must keep once you implement it for real.
"""

from __future__ import annotations

from agent_workspaces.models import SandboxState, WorkspaceRequest
from agent_workspaces.orchestrator import Orchestrator


async def test_create_workspace_assembles_all_planes(
    orchestrator: Orchestrator, sample_request: WorkspaceRequest
) -> None:
    ws = await orchestrator.create_workspace(sample_request)

    assert ws.id.startswith("ws_")
    assert ws.trace_id.startswith("tr_")
    assert ws.sandbox.state is SandboxState.RUNNING  # execution attached
    assert len(ws.data_branch_ids) == len(sample_request.datasets)


async def test_execute_runs_and_tears_down(
    orchestrator: Orchestrator, sample_request: WorkspaceRequest
) -> None:
    result = await orchestrator.execute(sample_request)

    assert result.succeeded is True
    assert result.exit_code == 0
    # Trace must survive after the sandbox is gone.
    events = await orchestrator.trace.load(result.trace_id)
    kinds = [e.kind for e in events]
    assert kinds[0] == "workspace.start"
    assert kinds[-1] == "workspace.end"


async def test_destroy_is_safe_to_call(
    orchestrator: Orchestrator, sample_request: WorkspaceRequest
) -> None:
    ws = await orchestrator.create_workspace(sample_request)
    await orchestrator.destroy_workspace(ws)
    # TODO: once teardown is real, assert the sandbox, data branches, proxy identity,
    #       and network rules are all actually gone (no leaks).


# TODO: add plane-level tests as you implement each backend, e.g.:
#   - warm pool: claim returns a compatible sandbox; cold path provisions on miss
#   - scheduler: release recycles only after a verified reset, else destroys
#   - security: secure() is a no-op-free path — proxy + policy applied before attach
#   - data: branch() fails loudly when no snapshot is configured
#   - trace: events persist across a simulated process restart (durable store)
