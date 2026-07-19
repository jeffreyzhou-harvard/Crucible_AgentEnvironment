"""Warm pool — pre-provisioned, ready-to-claim sandboxes.

Keeping sandboxes hot is what turns a multi-second cold start into an instant
attach. The pool continuously refills toward a demand-driven target and evicts
sandboxes that have sat idle past their TTL (LRU-style).

The pool is runtime-backed: when composed with the Docker execution plane it
*actually boots containers* ahead of demand (via the ``boot``/``destroy``
callables injected by the composition root), so a warm claim hands back a
sandbox whose environment is already running. With the mock runtime the same
machinery runs, just with model-only sandboxes — the lifecycle and the metrics
are identical either way.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from ..config import Settings
from ..models import Sandbox, SandboxState, WorkspaceRequest
from .shapes import shape_key_for_request, shape_key_for_sandbox, shapes_match

logger = logging.getLogger(__name__)

# Injected by the composition root. `boot` turns a base image into a live
# runtime_ref (e.g. a running container id); `destroy` reclaims one.
BootFn = Callable[[str], Awaitable[str | None]]
DestroyFn = Callable[[str], Awaitable[None]]


def _now() -> datetime:
    return datetime.now(UTC)


class WarmPool:
    """A bounded pool of WARM sandboxes plus a background refill loop."""

    def __init__(
        self,
        settings: Settings,
        *,
        boot: BootFn | None = None,
        destroy: DestroyFn | None = None,
        target_fn: Callable[[], Awaitable[int]] | None = None,
    ) -> None:
        self.settings = settings
        self._boot = boot
        self._destroy = destroy
        self._target_fn = target_fn
        self._warm: dict[str, Sandbox] = {}
        self._warmed_at: dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        self._wake = asyncio.Event()  # poked on claim so refill reacts immediately
        # Counters surfaced via /v1/pool — the control plane's speed receipts.
        self.hits = 0
        self.misses = 0
        self.provisioned = 0
        self.evicted = 0

    # --- claim / release -------------------------------------------------- #
    async def claim(self, request: WorkspaceRequest) -> Sandbox | None:
        """Take a shape-compatible warm sandbox out of the pool, or None.

        A warm sandbox is only reusable if it provides what the request needs
        (base image today; tooling + datasets as those become part of the
        shape). Handing back an incompatible sandbox would silently break
        fidelity, so mismatch = miss.
        """
        wanted = shape_key_for_request(request, self.settings)
        async with self._lock:
            for sid, sandbox in list(self._warm.items()):
                if not shapes_match(shape_key_for_sandbox(sandbox), wanted):
                    continue
                del self._warm[sid]
                self._warmed_at.pop(sid, None)
                sandbox.state = SandboxState.CLAIMED
                sandbox.claimed_at = _now()
                sandbox.warm_hit = True
                self.hits += 1
                self._wake.set()  # let the refill loop replace it right away
                return sandbox
            self.misses += 1
            return None

    async def release(self, sandbox: Sandbox) -> None:
        """Return a sandbox after use.

        Recycling is only safe after a verified reset to snapshot-equivalent
        state (fs, processes, data branches all reverted). Until reset exists,
        always destroy — isolation and reproducibility beat the latency win of
        an unsafe reuse. The refill loop replaces the capacity within a tick.
        """
        sandbox.state = SandboxState.DESTROYED

    # --- provisioning ----------------------------------------------------- #
    async def provision_now(self, request: WorkspaceRequest) -> Sandbox:
        """Cold-start a sandbox on the request path (pool miss)."""
        base_image = _base_image_for(request, self.settings)
        return await self._provision(base_image)

    async def _provision(self, base_image: str | None = None) -> Sandbox:
        """Create one sandbox from the versioned base snapshot.

        When a ``boot`` callable is wired (Docker composition), this is where
        the real cost lives — the container is started *here*, off the request
        path, so a later claim is a pointer swap instead of a boot.
        """
        image = base_image or self.settings.sandbox_base_image
        runtime_ref: str | None = None
        if self._boot is not None:
            runtime_ref = await self._boot(image)
        sandbox = Sandbox(
            id=f"sbx_{uuid.uuid4().hex[:12]}",
            state=SandboxState.WARM,
            base_image=image,
            created_at=_now(),
            runtime_ref=runtime_ref,
        )
        self.provisioned += 1
        return sandbox

    async def ensure_warm(self, base_image: str | None = None) -> bool:
        """Speculatively warm one sandbox for `base_image` (intent prediction).

        Returns True if a sandbox was provisioned; False if one was already
        warm for that shape or the pool is at capacity — so a burst of intent
        signals can't exhaust capacity.
        """
        image = base_image or self.settings.sandbox_base_image
        async with self._lock:
            if len(self._warm) >= self.settings.warm_pool_max_size:
                return False
            if any(s.base_image == image for s in self._warm.values()):
                return False
        sandbox = await self._provision(image)
        async with self._lock:
            if len(self._warm) >= self.settings.warm_pool_max_size:
                await self._destroy_sandbox(sandbox)
                return False
            self._warm[sandbox.id] = sandbox
            self._warmed_at[sandbox.id] = _now()
        return True

    async def _destroy_sandbox(self, sandbox: Sandbox) -> None:
        if self._destroy is not None and sandbox.runtime_ref:
            try:
                await self._destroy(sandbox.runtime_ref)
            except Exception:  # noqa: BLE001 — eviction is best-effort cleanup
                logger.warning("failed to destroy evicted sandbox %s", sandbox.id)
        sandbox.state = SandboxState.DESTROYED

    # --- background maintenance ------------------------------------------ #
    async def run(self) -> None:
        """Refill/evict loop. Started as a background task from the app lifespan.

        Refills toward the demand-predicted target (floored at min_size, capped
        at max_size), evicts sandboxes idle past their TTL, and backs off
        exponentially if provisioning starts failing so a broken backend can't
        hot-loop the host.
        """
        backoff = 1.0
        while True:
            try:
                await self._evict_idle()
                target = await self._target()
                async with self._lock:
                    deficit = target - len(self._warm)
                for _ in range(max(0, deficit)):
                    sandbox = await self._provision()
                    async with self._lock:
                        if len(self._warm) < self.settings.warm_pool_max_size:
                            self._warm[sandbox.id] = sandbox
                            self._warmed_at[sandbox.id] = _now()
                        else:
                            await self._destroy_sandbox(sandbox)
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — keep the loop alive; alert and back off
                logger.exception("warm pool refill failed; backing off %.0fs", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
                continue
            # Event-driven cadence: react instantly to a claim, otherwise idle.
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=2.0)
            except TimeoutError:
                pass

    async def _target(self) -> int:
        floor = self.settings.warm_pool_min_size
        target = floor
        if self._target_fn is not None:
            target = max(floor, await self._target_fn())
        return min(target, self.settings.warm_pool_max_size)

    async def _evict_idle(self) -> None:
        ttl = self.settings.warm_pool_idle_ttl_seconds
        now = _now()
        stale: list[Sandbox] = []
        async with self._lock:
            for sid, warmed_at in list(self._warmed_at.items()):
                if (now - warmed_at).total_seconds() > ttl:
                    stale.append(self._warm.pop(sid))
                    del self._warmed_at[sid]
                    self.evicted += 1
        for sandbox in stale:
            await self._destroy_sandbox(sandbox)

    async def drain(self) -> None:
        """Destroy every warm sandbox (app shutdown). Idempotent."""
        async with self._lock:
            sandboxes = list(self._warm.values())
            self._warm.clear()
            self._warmed_at.clear()
        for sandbox in sandboxes:
            await self._destroy_sandbox(sandbox)

    async def size(self) -> int:
        async with self._lock:
            return len(self._warm)

    async def stats(self) -> dict[str, object]:
        """Pool observability for GET /v1/pool."""
        async with self._lock:
            warm = [
                {
                    "id": s.id,
                    "base_image": s.base_image,
                    "booted": s.runtime_ref is not None,
                    "age_seconds": round((_now() - self._warmed_at[s.id]).total_seconds(), 1),
                }
                for s in self._warm.values()
            ]
        return {
            "size": len(warm),
            "min_size": self.settings.warm_pool_min_size,
            "max_size": self.settings.warm_pool_max_size,
            "hits": self.hits,
            "misses": self.misses,
            "provisioned": self.provisioned,
            "evicted": self.evicted,
            "hit_rate": round(self.hits / (self.hits + self.misses), 3)
            if (self.hits + self.misses)
            else None,
            "warm": warm,
        }


def _base_image_for(request: WorkspaceRequest, settings: Settings) -> str:
    hint = request.scheduling_hints.get("base_image")
    return str(hint) if hint else settings.sandbox_base_image
