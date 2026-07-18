"""Intent prediction — provision *before* the request formally arrives.

The single biggest latency win: start preparing a sandbox while the user is still
composing their prompt. By the time they hit "go", the environment is warm and
shaped for the task. If the prediction is wrong, the speculative sandbox is cheap
to discard (it just goes back to / falls out of the warm pool).
"""

from __future__ import annotations

from ..config import Settings
from ..models import WorkspaceRequest
from .warm_pool import WarmPool


class IntentPredictor:
    """Turns early, partial signals into speculative provisioning."""

    def __init__(self, warm_pool: WarmPool, settings: Settings) -> None:
        self.warm_pool = warm_pool
        self.settings = settings

    async def on_signal(self, partial: dict[str, object]) -> None:
        """Called as soon as we see intent (keystrokes, repo focus, editor context).

        TODO:
          - infer the likely request "shape" from `partial` (repo, language, datasets)
          - speculatively warm a matching sandbox via the pool
          - de-duplicate: don't warm 10 sandboxes for one hesitating user
          - cap speculative provisioning so a burst of signals can't exhaust capacity
        """
        raise NotImplementedError

    def shape_key(self, request: WorkspaceRequest) -> str:
        """A stable key describing what a sandbox must provide to serve `request`.

        The warm pool and the predictor must agree on this key so a speculatively
        warmed sandbox can actually be claimed when the real request lands.

        TODO: derive from base image + repos + dataset kinds + tooling. Keep it
        coarse enough to get pool hits, precise enough to preserve fidelity.
        """
        raise NotImplementedError
