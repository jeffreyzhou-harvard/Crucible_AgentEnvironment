"""FastAPI entrypoint for the control-plane API.

Run with:  uvicorn agent_workspaces.main:app --reload
Or:        agent-workspaces   (see [project.scripts] in pyproject.toml)

`build_orchestrator()` is the composition root: it picks the concrete plane
implementations from settings. For the MVP, the EXECUTION and TRACE planes are real
(Docker + streaming) while the CONTROL, SECURITY, and DATA planes are still mocks —
swap those in as you implement them.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import Settings, get_settings
from .control.scheduler import InMemoryScheduler, Scheduler
from .control.warm_pool import WarmPool
from .data.provisioner import DataPlane, MockDataPlane
from .execution.sandbox import DockerSandboxRuntime, MockSandboxRuntime, SandboxRuntime
from .orchestrator import Orchestrator
from .security.isolation import MockSecurityPlane, ProxyingSecurityPlane, SecurityPlane
from .trace.bus import TraceBus
from .trace.recorder import InMemoryTraceRecorder, TraceRecorder


def build_orchestrator(settings: Settings | None = None, bus: TraceBus | None = None) -> Orchestrator:
    """Pick concrete backends per settings and wire them up.

    EXECUTION: real Docker runtime when AWS_RUNTIME_BACKEND=docker, else mock.
    CONTROL / SECURITY / DATA: still mocks in the MVP — implement and swap here.
    """
    settings = settings or get_settings()

    warm_pool = WarmPool(settings=settings)
    scheduler: Scheduler = InMemoryScheduler(warm_pool=warm_pool, settings=settings)

    runtime: SandboxRuntime
    if settings.runtime_backend == "docker":
        runtime = DockerSandboxRuntime(settings=settings)
    else:
        runtime = MockSandboxRuntime(settings=settings)

    security: SecurityPlane
    if settings.security_backend == "proxy":
        security = ProxyingSecurityPlane(settings=settings)
    else:
        security = MockSecurityPlane(settings=settings)

    data: DataPlane = MockDataPlane(settings=settings)
    trace: TraceRecorder = InMemoryTraceRecorder(settings=settings, bus=bus)

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
    bus = TraceBus()
    app.state.trace_bus = bus
    app.state.orchestrator = build_orchestrator(bus=bus)
    # Track background lifecycle tasks so they aren't garbage-collected mid-run.
    app.state.tasks = set()
    # TODO: start the warm-pool refill loop + demand predictor here for real speed.
    yield
    # Stop the shared egress proxy if the security plane started one.
    security = getattr(app.state.orchestrator, "security", None)
    shutdown = getattr(security, "shutdown", None)
    if callable(shutdown):
        shutdown()
    # TODO: on shutdown, also cancel in-flight tasks and destroy every live sandbox.


app = FastAPI(title="agent-workspaces control plane", version="0.1.0", lifespan=lifespan)

# TODO: lock CORS down to the deployed frontend origin. Open for local dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
