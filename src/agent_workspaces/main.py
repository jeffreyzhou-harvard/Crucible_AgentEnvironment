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
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import Settings, get_settings
from .control.intent import IntentPredictor
from .control.scheduler import DemandPredictor, InMemoryScheduler, Scheduler
from .control.warm_pool import WarmPool
from .data.provisioner import CowDataPlane, DataPlane, MockDataPlane
from .execution.sandbox import DockerSandboxRuntime, MockSandboxRuntime, SandboxRuntime
from .orchestrator import Orchestrator
from .security.isolation import MockSecurityPlane, ProxyingSecurityPlane, SecurityPlane
from .trace.bus import TraceBus
from .trace.recorder import InMemoryTraceRecorder, JsonlTraceRecorder, TraceRecorder


def _load_agent_credentials_from_dotenv() -> None:
    """Make the Anthropic SDK's env vars available for local dev.

    pydantic-settings loads `.env` into `Settings`, but the Anthropic client reads
    ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN straight from the process environment.
    We bridge only those (never overriding what's already exported), so `make dev`
    picks up the key from `.env` without a manual `export`.
    """
    dotenv = Path(get_settings().model_config.get("env_file", ".env"))
    if not dotenv.is_file():
        return
    wanted = {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"}
    for raw in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in wanted and key not in os.environ:
            os.environ[key] = value.split(" #")[0].strip().strip('"').strip("'")


_load_agent_credentials_from_dotenv()


def build_orchestrator(settings: Settings | None = None, bus: TraceBus | None = None) -> Orchestrator:
    """Pick concrete backends per settings and wire them up.

    EXECUTION: real Docker runtime when AWS_RUNTIME_BACKEND=docker, else mock.
    CONTROL:   real runtime-backed warm pool (boots containers ahead of demand
               under docker) + EWMA demand predictor + intent predictor.
    SECURITY:  real egress proxy when AWS_SECURITY_BACKEND=proxy, else mock.
    DATA:      real CoW branching when AWS_DATA_BRANCH_BACKEND=cow, else mock.
    TRACE:     durable JSONL store when AWS_TRACE_STORE_URI is set, else memory.
    """
    settings = settings or get_settings()

    runtime: SandboxRuntime
    if settings.runtime_backend == "docker":
        runtime = DockerSandboxRuntime(settings=settings)
    else:
        runtime = MockSandboxRuntime(settings=settings)

    # The warm pool boots real environments ahead of demand when the runtime
    # can (docker); with the mock runtime it models the same lifecycle.
    docker_runtime = runtime if isinstance(runtime, DockerSandboxRuntime) else None
    predictor = DemandPredictor(settings=settings)
    warm_pool = WarmPool(
        settings=settings,
        boot=docker_runtime.backend.restore_from_snapshot if docker_runtime else None,
        destroy=docker_runtime.backend.destroy if docker_runtime else None,
        target_fn=predictor.predict,
    )
    scheduler: Scheduler = InMemoryScheduler(
        warm_pool=warm_pool, settings=settings, predictor=predictor
    )

    security: SecurityPlane
    if settings.security_backend == "proxy":
        security = ProxyingSecurityPlane(settings=settings)
    else:
        security = MockSecurityPlane(settings=settings)

    data: DataPlane
    if settings.data_branch_backend == "cow":
        data = CowDataPlane(settings=settings)
    else:
        data = MockDataPlane(settings=settings)

    trace: TraceRecorder
    if settings.trace_store_uri:
        trace = JsonlTraceRecorder(settings=settings, bus=bus)
    else:
        trace = InMemoryTraceRecorder(settings=settings, bus=bus)

    return Orchestrator(
        scheduler=scheduler,
        runtime=runtime,
        security=security,
        data=data,
        trace=trace,
        settings=settings,
        warm_pool=warm_pool,
        intent=IntentPredictor(warm_pool=warm_pool, settings=settings),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    bus = TraceBus()
    app.state.trace_bus = bus
    app.state.settings = get_settings()
    orchestrator = build_orchestrator(bus=bus)
    app.state.orchestrator = orchestrator
    # Track background lifecycle tasks so they aren't garbage-collected mid-run.
    app.state.tasks = set()
    # Start the warm-pool refill loop: sandboxes are provisioned (and, under
    # docker, actually booted) ahead of demand, sized by the demand predictor.
    refill_task: asyncio.Task | None = None
    if orchestrator.warm_pool is not None:
        refill_task = asyncio.create_task(orchestrator.warm_pool.run(), name="warm-pool-refill")
    yield
    # Cancel in-flight lifecycle/experiment tasks so shutdown doesn't strand them.
    tasks: set[asyncio.Task] = app.state.tasks
    for task in list(tasks):
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    if refill_task is not None:
        refill_task.cancel()
        await asyncio.gather(refill_task, return_exceptions=True)
    # Destroy every still-live sandbox, then drain the warm pool — a leaked
    # container outliving the control plane is an isolation incident.
    for workspace_id in list(orchestrator.live):
        try:
            await orchestrator.destroy_workspace(workspace_id)
        except Exception:  # noqa: BLE001 — best-effort cleanup on shutdown
            pass
    if orchestrator.warm_pool is not None:
        await orchestrator.warm_pool.drain()
    # Stop the shared egress proxy if the security plane started one.
    shutdown = getattr(orchestrator.security, "shutdown", None)
    if callable(shutdown):
        shutdown()


app = FastAPI(title="Crucible control plane", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
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
