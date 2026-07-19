"""Control-plane HTTP + WebSocket routes.

Thin layer: validate input, kick off the lifecycle, stream the trace. Business
logic lives in the planes, not here.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect

from ..config import Settings, get_settings
from ..experiment.runner import new_experiment_ids, run_experiment
from ..models import (
    ExperimentLaunchResponse,
    ExperimentRequest,
    LaunchResponse,
    TraceEvent,
    WorkspaceRequest,
)
from ..orchestrator import Orchestrator
from ..trace.bus import TraceBus

router = APIRouter(prefix="/v1", tags=["workspaces"])

_TERMINAL_KINDS = {"workspace.end", "experiment.end"}


def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator  # type: ignore[no-any-return]


def get_app_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", None) or get_settings()


def require_api_key(
    request: Request, settings: Settings = Depends(get_app_settings)
) -> None:
    """Reject callers when an API key is configured and not presented.

    Open by default (empty `api_key`) for local dev; set `AWS_API_KEY` to require an
    `X-API-Key` header on the launch endpoints.
    """
    if not settings.api_key:
        return
    provided = request.headers.get("x-api-key", "")
    if provided != settings.api_key:
        raise HTTPException(status_code=401, detail="invalid or missing API key")


@router.post("/workspaces:launch", response_model=LaunchResponse)
async def launch(
    body: WorkspaceRequest,
    request: Request,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    _: None = Depends(require_api_key),
) -> LaunchResponse:
    """Start a workspace and return its ids immediately.

    The lifecycle (provision → secure → run agent → tear down) runs in the
    background; connect to `/v1/traces/{trace_id}/stream` to watch it live.
    """
    # TODO: enforce per-tenant quotas here (auth is handled by require_api_key).
    workspace_id, trace_id = await orchestrator.begin(body)

    task = asyncio.create_task(orchestrator.run_lifecycle(body, workspace_id, trace_id))
    tasks: set = request.app.state.tasks
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    # Keep a handle per workspace so :destroy can cancel the running lifecycle.
    workspace_tasks: dict = getattr(request.app.state, "workspace_tasks", None) or {}
    request.app.state.workspace_tasks = workspace_tasks
    workspace_tasks[workspace_id] = task
    task.add_done_callback(lambda _t, wid=workspace_id: workspace_tasks.pop(wid, None))

    return LaunchResponse(workspace_id=workspace_id, trace_id=trace_id)


@router.get("/security/egress-audit")
async def egress_audit(
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> dict:
    """Return the egress audit log: every allow/block decision the proxy has made.

    Empty + ``enforced: false`` when the mock security plane is active (no proxy).
    """
    audit = getattr(orchestrator.security, "audit", None)
    if audit is None:
        return {"enforced": False, "entries": []}
    return {"enforced": True, "entries": audit.entries()}


@router.post("/experiments:launch", response_model=ExperimentLaunchResponse)
async def launch_experiment(
    body: ExperimentRequest,
    request: Request,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    _: None = Depends(require_api_key),
) -> ExperimentLaunchResponse:
    """Start a best-of-N experiment and return its ids immediately.

    N candidates race in parallel; each is scored against a held-out grader. Watch it
    live at `/v1/traces/{trace_id}/stream`.
    """
    experiment_id, trace_id = new_experiment_ids()
    # Share the security plane's audit log so experiment egress attempts show up in
    # GET /v1/security/egress-audit alongside single-run traffic (proxy backend only).
    audit = getattr(orchestrator.security, "audit", None)
    task = asyncio.create_task(
        run_experiment(
            orchestrator.trace, orchestrator.settings, body, experiment_id, trace_id, audit=audit
        )
    )
    tasks: set = request.app.state.tasks
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return ExperimentLaunchResponse(experiment_id=experiment_id, trace_id=trace_id)


@router.websocket("/traces/{trace_id}/stream")
async def stream_trace(websocket: WebSocket, trace_id: str) -> None:
    """Stream a trace: full history so far, then live until a terminal event."""
    await websocket.accept()
    bus: TraceBus = websocket.app.state.trace_bus
    history, queue = await bus.subscribe(trace_id)

    def to_json(event: TraceEvent) -> dict:
        return event.model_dump(mode="json")

    try:
        ended = False
        for event in history:
            await websocket.send_json(to_json(event))
            if event.kind in _TERMINAL_KINDS:
                ended = True
        while not ended:
            event = await queue.get()
            await websocket.send_json(to_json(event))
            if event.kind in _TERMINAL_KINDS:
                break
    except WebSocketDisconnect:
        pass
    except RuntimeError:
        # Client closed the socket between our reads/sends (e.g. React StrictMode's
        # dev double-mount opens+closes a duplicate connection). Not an error.
        pass
    finally:
        await bus.unsubscribe(trace_id, queue)


@router.get("/traces/{trace_id}")
async def get_trace(
    trace_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> dict:
    """Fetch a recorded trajectory for replay / evaluation.

    With the durable store (AWS_TRACE_STORE_URI) this survives process
    restarts — the sandbox is gone, the trace remains.
    """
    events = await orchestrator.trace.load(trace_id)
    if not events:
        raise HTTPException(status_code=404, detail=f"no trace {trace_id!r}")
    return {"trace_id": trace_id, "events": [e.model_dump(mode="json") for e in events]}


@router.get("/pool")
async def pool_stats(
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> dict:
    """Warm-pool observability: size, hit rate, and what's currently hot."""
    if orchestrator.warm_pool is None:
        return {"enabled": False}
    stats = await orchestrator.warm_pool.stats()
    return {"enabled": True, **stats}


@router.post("/intent:signal")
async def intent_signal(
    body: dict,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> dict:
    """Early-intent hook: the UI calls this the moment a user starts composing
    a request, so a shaped sandbox can be warming before they hit launch."""
    if orchestrator.intent is None:
        return {"warmed": False}
    warmed = await orchestrator.intent.on_signal(body or {})
    return {"warmed": warmed}


@router.post("/workspaces/{workspace_id}:destroy")
async def destroy_workspace(
    workspace_id: str,
    request: Request,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    _: None = Depends(require_api_key),
) -> dict:
    """Force teardown of a live workspace: cancel its lifecycle, reclaim the
    sandbox. Idempotent — destroying an unknown/finished workspace is a no-op."""
    workspace_tasks: dict = getattr(request.app.state, "workspace_tasks", {}) or {}
    task = workspace_tasks.pop(workspace_id, None)
    if task is not None and not task.done():
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    destroyed = await orchestrator.destroy_workspace(workspace_id)
    return {"workspace_id": workspace_id, "destroyed": destroyed or task is not None}
