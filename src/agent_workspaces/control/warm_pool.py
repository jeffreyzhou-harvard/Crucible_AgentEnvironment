"""Warm pool — pre-provisioned, ready-to-claim sandboxes.

Keeping sandboxes hot is what turns a multi-second cold start into an instant
attach. The pool continuously refills toward a demand-driven target and evicts
sandboxes that have sat idle past their TTL (LRU-style).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from ..config import Settings
from ..models import Sandbox, SandboxState, WorkspaceRequest


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WarmPool:
    """A bounded pool of WARM sandboxes plus a background refill loop.

    NOTE: this reference implementation only *models* sandboxes — it never boots a
    real environment. Wire `provision_now` and `_provision` to the execution
    runtime to make it real.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._warm: dict[str, Sandbox] = {}
        self._lock = asyncio.Lock()

    # --- claim / release -------------------------------------------------- #
    async def claim(self, request: WorkspaceRequest) -> Sandbox | None:
        """Take a compatible warm sandbox out of the pool, or None if none fit."""
        async with self._lock:
            # TODO: match on the request "shape" (base image + tooling + datasets),
            #       not just "any warm sandbox". Returning an incompatible sandbox
            #       silently breaks fidelity.
            for sid, sandbox in list(self._warm.items()):
                del self._warm[sid]
                sandbox.state = SandboxState.CLAIMED
                sandbox.claimed_at = _now()
                return sandbox
            return None

    async def release(self, sandbox: Sandbox) -> None:
        """Return a sandbox to the pool (if recyclable) or drop it."""
        async with self._lock:
            # TODO: only recycle after a verified reset to snapshot-equivalent state.
            #       Until reset is implemented, always destroy to preserve isolation.
            sandbox.state = SandboxState.DESTROYED

    # --- provisioning ----------------------------------------------------- #
    async def provision_now(self, request: WorkspaceRequest) -> Sandbox:
        """Cold-start a sandbox on the request path (pool miss)."""
        return await self._provision()

    async def _provision(self) -> Sandbox:
        """Create one sandbox from the versioned base snapshot.

        TODO: this is where the real cost lives. Delegate to the execution runtime
        to restore `settings.sandbox_base_image`, boot services, and run a health
        check before marking the sandbox WARM. Only healthy sandboxes enter the pool.
        """
        sandbox = Sandbox(
            id=f"sbx_{uuid.uuid4().hex[:12]}",
            state=SandboxState.WARM,
            base_image=self.settings.sandbox_base_image,
            created_at=_now(),
            runtime_ref=None,  # TODO: set to the backend handle once provisioned
        )
        return sandbox

    # --- background maintenance ------------------------------------------ #
    async def run(self) -> None:
        """Refill/evict loop. Start as a background task from the app lifespan.

        TODO:
          - refill toward DemandPredictor.predict() up to warm_pool_max_size
          - evict sandboxes idle > warm_pool_idle_ttl_seconds (LRU)
          - back off and alert if provisioning starts failing
        """
        while True:
            async with self._lock:
                deficit = self.settings.warm_pool_min_size - len(self._warm)
            for _ in range(max(0, deficit)):
                sandbox = await self._provision()
                async with self._lock:
                    if len(self._warm) < self.settings.warm_pool_max_size:
                        self._warm[sandbox.id] = sandbox
            # TODO: replace the fixed sleep with an event-driven or adaptive cadence.
            await asyncio.sleep(1.0)

    async def size(self) -> int:
        async with self._lock:
            return len(self._warm)
