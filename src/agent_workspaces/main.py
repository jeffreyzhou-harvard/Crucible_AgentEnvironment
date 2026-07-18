"""FastAPI entrypoint for the control-plane API.

Run with:  uvicorn agent_workspaces.main:app --reload
Or:        agent-workspaces   (see [project.scripts] in pyproject.toml)

This module also contains `build_orchestrator()`, the composition root where the
concrete plane implementations are chosen based on settings. Swap the mock
backends here as you implement each plane.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from .api.routes import router
from .config import Settings, get_settings
from .control.scheduler import InMemoryScheduler, Scheduler
from .control.warm_pool import WarmPool
from .data.provisioner import DataPlane, MockDataPlane
from .execution.sandbox import MockSandboxRuntime, SandboxRuntime
from .orchestrator import Orchestrator
from .security.isolation import MockSecurityPlane, SecurityPlane
from .trace.recorder import InMemoryTraceRecorder, TraceRecorder


def build_orchestrator(settings: Settings | None = None) -> Orchestrator:
    """Composition root: pick concrete backends per settings and wire them up.

    TODO: select real implementations based on settings.runtime_backend,
    settings.data_branch_backend, etc. For now everything is a mock so the API
    boots and the lifecycle is exercisable end-to-end without infrastructure.
    """
    settings = settings or get_settings()

    warm_pool = WarmPool(settings=settings)
    scheduler: Scheduler = InMemoryScheduler(warm_pool=warm_pool, settings=settings)
    runtime: SandboxRuntime = MockSandboxRuntime(settings=settings)
    security: SecurityPlane = MockSecurityPlane(settings=settings)
    data: DataPlane = MockDataPlane(settings=settings)
    trace: TraceRecorder = InMemoryTraceRecorder(settings=settings)

    return Orchestrator(
        scheduler=scheduler,
        runtime=runtime,
        security=security,
        data=data,
        trace=trace,
        settings=settings,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start/stop background work owned by the control plane."""
    orchestrator = build_orchestrator()
    app.state.orchestrator = orchestrator
    # TODO: start the warm-pool refill loop and the demand predictor here.
    #       e.g. task = asyncio.create_task(orchestrator.scheduler.warm_pool.run())
    yield
    # TODO: drain in-flight workspaces and destroy all sandboxes on shutdown.


app = FastAPI(title="agent-workspaces control plane", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


def run() -> None:
    """Console-script entrypoint (`agent-workspaces`)."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "agent_workspaces.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.env == "local",
    )
