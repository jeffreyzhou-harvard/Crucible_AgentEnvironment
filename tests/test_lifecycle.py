"""End-to-end lifecycle tests against the mock planes.

These pass today with the scaffold's mocks. They double as executable documentation
of the contract the streaming lifecycle keeps: plane events fire in order, the agent
runs, and the trace is sealed with `workspace.end`.
"""

from __future__ import annotations

from agent_workspaces.models import WorkspaceRequest
from agent_workspaces.orchestrator import Orchestrator


async def test_execute_runs_full_lifecycle(
    orchestrator: Orchestrator, sample_request: WorkspaceRequest
) -> None:
    result = await orchestrator.execute(sample_request)

    assert result is not None
    assert result.succeeded is True
    assert result.workspace_id.startswith("ws_")

    events = await orchestrator.trace.load(result.trace_id)
    kinds = [e.kind for e in events]

    # Trace opens and closes cleanly.
    assert kinds[0] == "workspace.start"
    assert kinds[-1] == "workspace.end"

    # All four planes fired, in order, before the agent ran.
    for plane in ("plane.control", "plane.data", "plane.security", "plane.execution"):
        assert plane in kinds, f"missing {plane}"
    assert kinds.index("plane.security") < kinds.index("plane.execution")
    assert kinds.index("plane.execution") < kinds.index("agent.start")


async def test_begin_returns_ids_and_opens_trace(
    orchestrator: Orchestrator, sample_request: WorkspaceRequest
) -> None:
    workspace_id, trace_id = await orchestrator.begin(sample_request)
    assert workspace_id.startswith("ws_")
    assert trace_id.startswith("tr_")

    events = await orchestrator.trace.load(trace_id)
    assert events and events[0].kind == "workspace.start"

    # The stream is watchable before the (background) lifecycle runs.
    result = await orchestrator.run_lifecycle(sample_request, workspace_id, trace_id)
    assert result is not None and result.workspace_id == workspace_id


# TODO: add plane-level tests as you implement each real backend, e.g.:
#   - docker runtime: attach() clones the repo; run_agent streams tool_call/output
#   - security: egress policy actually blocks a non-allowlisted host
#   - data: branch() fails loudly when no snapshot is configured
#   - trace: events survive a simulated process restart (durable store)
