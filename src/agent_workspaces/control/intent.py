"""Intent prediction — provision *before* the request formally arrives.

The single biggest latency win: start preparing a sandbox while the user is still
composing their prompt. By the time they hit "go", the environment is warm and
shaped for the task. If the prediction is wrong, the speculative sandbox is cheap
to discard (it just goes back to / falls out of the warm pool).
"""

from __future__ import annotations

import asyncio

from ..config import Settings
from ..models import WorkspaceRequest
from .shapes import shape_key_for_request
from .warm_pool import WarmPool


class IntentPredictor:
    """Turns early, partial signals into speculative provisioning."""

    #: Cap on concurrently in-flight speculative provisions, so a burst of
    #: signals (or one hesitating user re-focusing a form) can't exhaust capacity.
    MAX_INFLIGHT = 2

    def __init__(self, warm_pool: WarmPool, settings: Settings) -> None:
        self.warm_pool = warm_pool
        self.settings = settings
        self._inflight: set[str] = set()
        self._lock = asyncio.Lock()
        self.signals = 0
        self.warmed = 0

    async def on_signal(self, partial: dict[str, object]) -> bool:
        """Called as soon as we see intent (form focus, keystrokes, repo focus).

        Infers the likely request shape from the partial signal and speculatively
        warms one matching sandbox. De-duplicates per shape and caps in-flight
        provisioning. Returns True if a sandbox was (newly) warmed.
        """
        self.signals += 1
        image = str(partial.get("base_image") or self.settings.sandbox_base_image)

        async with self._lock:
            if image in self._inflight or len(self._inflight) >= self.MAX_INFLIGHT:
                return False  # already warming this shape, or at the speculation cap
            self._inflight.add(image)
        try:
            warmed = await self.warm_pool.ensure_warm(image)
            if warmed:
                self.warmed += 1
            return warmed
        finally:
            async with self._lock:
                self._inflight.discard(image)

    def shape_key(self, request: WorkspaceRequest) -> str:
        """A stable key describing what a sandbox must provide to serve `request`.

        Shared with the warm pool and scheduler (see `control/shapes.py`) so a
        speculatively warmed sandbox can actually be claimed when the real
        request lands.
        """
        return shape_key_for_request(request, self.settings)
