"""Scheduler — the control plane's public interface.

The scheduler decides *which* sandbox serves a request: hand back a compatible warm
one instantly, or provision a fresh one from a versioned snapshot when the pool is
empty or nothing matches.
"""

from __future__ import annotations

import abc

from ..config import Settings
from ..models import Sandbox, WorkspaceRequest
from .warm_pool import WarmPool


class Scheduler(abc.ABC):
    """Assigns sandboxes to requests and reclaims them afterwards."""

    @abc.abstractmethod
    async def acquire(self, request: WorkspaceRequest) -> Sandbox:
        """Return a ready sandbox for `request`.

        Fast path: a compatible WARM sandbox from the pool.
        Slow path: provision one from the base snapshot (cold start).
        """

    @abc.abstractmethod
    async def release(self, sandbox: Sandbox) -> None:
        """Reclaim a sandbox after use: recycle into the pool or destroy it."""


class InMemoryScheduler(Scheduler):
    """Reference scheduler backed by an in-process warm pool.

    Good enough to exercise the lifecycle in tests; NOT suitable for real load.
    """

    def __init__(self, warm_pool: WarmPool, settings: Settings) -> None:
        self.warm_pool = warm_pool
        self.settings = settings

    async def acquire(self, request: WorkspaceRequest) -> Sandbox:
        # TODO: matching logic. A warm sandbox is only reusable if its base image,
        #       mounted tooling, and pre-provisioned services match the request.
        #       Compute a "shape key" from the request and look for a warm match.
        sandbox = await self.warm_pool.claim(request)
        if sandbox is not None:
            return sandbox
        # Cold path: nothing warm matched.
        # TODO: provision from settings.sandbox_base_image via the execution runtime.
        return await self.warm_pool.provision_now(request)

    async def release(self, sandbox: Sandbox) -> None:
        # TODO: decide recycle-vs-destroy. Recycling is only safe if the sandbox can
        #       be reset to a clean, snapshot-equivalent state (fs, processes, data
        #       branches all reverted). If in doubt, destroy — reproducibility and
        #       isolation beat the latency win of an unsafe reuse.
        await self.warm_pool.release(sandbox)


class DemandPredictor:
    """Predicts near-future sandbox demand so the warm pool can pre-scale.

    Feeds the warm pool's refill loop. Signals might include time-of-day, per-tenant
    request history, and live intent signals (see intent.py).
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def predict(self) -> int:
        """Return the number of warm sandboxes to target right now.

        TODO: replace the constant floor with a real forecast (EWMA of recent
        arrivals, a small time-series model, or a per-tenant reservation scheme).
        """
        return self.settings.warm_pool_min_size
