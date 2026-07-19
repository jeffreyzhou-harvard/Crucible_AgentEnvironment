"""Scheduler — the control plane's public interface.

The scheduler decides *which* sandbox serves a request: hand back a compatible warm
one instantly, or provision a fresh one from a versioned snapshot when the pool is
empty or nothing matches.
"""

from __future__ import annotations

import abc
import math
import time
from collections import deque

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

    def __init__(
        self,
        warm_pool: WarmPool,
        settings: Settings,
        predictor: DemandPredictor | None = None,
    ) -> None:
        self.warm_pool = warm_pool
        self.settings = settings
        self.predictor = predictor

    async def acquire(self, request: WorkspaceRequest) -> Sandbox:
        # Every arrival feeds the demand forecast so the pool pre-scales.
        if self.predictor is not None:
            self.predictor.record_arrival()
        # Fast path: a warm sandbox whose shape (base image + tooling) matches.
        sandbox = await self.warm_pool.claim(request)
        if sandbox is not None:
            return sandbox
        # Cold path: nothing warm matched — provision on the request path.
        # With the Docker composition this boots a real container (the latency
        # the warm pool exists to hide); the trace records it as warm_hit=false.
        return await self.warm_pool.provision_now(request)

    async def release(self, sandbox: Sandbox) -> None:
        # Recycling is only safe if the sandbox can be reset to a clean,
        # snapshot-equivalent state (fs, processes, data branches all reverted).
        # No verified reset exists yet, so the pool always destroys —
        # reproducibility and isolation beat the latency win of an unsafe reuse.
        await self.warm_pool.release(sandbox)


class DemandPredictor:
    """Predicts near-future sandbox demand so the warm pool can pre-scale.

    Feeds the warm pool's refill loop. Uses an exponentially-weighted moving
    average of the recent arrival rate: the pool targets enough warm sandboxes
    to absorb the next `horizon_seconds` of predicted arrivals, floored at
    `warm_pool_min_size` and capped by the pool itself at `warm_pool_max_size`.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        horizon_seconds: float = 60.0,
        window_seconds: float = 300.0,
    ) -> None:
        self.settings = settings
        self.horizon = horizon_seconds
        self.window = window_seconds
        self._arrivals: deque[float] = deque(maxlen=256)
        self._rate_ewma = 0.0  # arrivals per second
        self._alpha = 0.3

    def record_arrival(self) -> None:
        now = time.monotonic()
        self._arrivals.append(now)
        # Instantaneous rate over the trailing window, folded into the EWMA.
        cutoff = now - self.window
        recent = sum(1 for t in self._arrivals if t >= cutoff)
        instant_rate = recent / self.window
        self._rate_ewma = self._alpha * instant_rate + (1 - self._alpha) * self._rate_ewma

    async def predict(self) -> int:
        """Warm sandboxes to target right now: forecast arrivals over the horizon."""
        forecast = math.ceil(self._rate_ewma * self.horizon)
        return max(self.settings.warm_pool_min_size, forecast)
