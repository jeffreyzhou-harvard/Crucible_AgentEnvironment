"""Control-plane HTTP routes.

Thin layer: validate input, delegate to the orchestrator, shape the response.
Business logic belongs in the planes, not here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..models import ExecutionResult, Workspace, WorkspaceRequest
from ..orchestrator import Orchestrator

router = APIRouter(prefix="/v1", tags=["workspaces"])


def get_orchestrator(request: Request) -> Orchestrator:
    """Pull the process-wide orchestrator off app state (set in lifespan)."""
    return request.app.state.orchestrator  # type: ignore[no-any-return]


@router.post("/workspaces", response_model=Workspace)
async def create_workspace(
    body: WorkspaceRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> Workspace:
    """Assemble a workspace and return its handle (does NOT run the agent yet)."""
    # TODO: authenticate the caller and enforce per-tenant quotas before creating.
    return await orchestrator.create_workspace(body)


@router.post("/workspaces:execute", response_model=ExecutionResult)
async def execute(
    body: WorkspaceRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> ExecutionResult:
    """One-shot: create → run → destroy. Returns the execution result.

    TODO: for long runs, make this async — return a workspace id immediately and
    stream results/trace over websocket or SSE instead of blocking the request.
    """
    return await orchestrator.execute(body)


# TODO: add the rest of the surface as you flesh out the planes:
#   GET  /v1/workspaces/{id}            -> current Workspace + SandboxState
#   POST /v1/workspaces/{id}:destroy    -> force teardown
#   GET  /v1/traces/{trace_id}          -> fetch a persisted trajectory (replay/eval)
#   GET  /v1/pool                       -> warm-pool stats (debugging the control plane)
