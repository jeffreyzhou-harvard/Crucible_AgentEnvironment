"""Health checks — prove the data is ready before the agent gets the sandbox.

Handing an agent a database that's still restoring, or a branch that came up empty,
produces failures that look like agent bugs. Gate handoff on a health check so a
green sandbox always means a genuinely ready environment.
"""

from __future__ import annotations

import abc

from ..config import Settings


class HealthChecker(abc.ABC):
    """Verifies provisioned data branches are ready and correct."""

    @abc.abstractmethod
    async def check(self, branch_ids: list[str]) -> bool:
        """Return True only if every branch is reachable and passes its checks.

        TODO:
          - connectivity + auth to each branch
          - migrations/schema at the expected version
          - a cheap sentinel query proving reference rows are present
          - bounded retries with backoff (services may still be warming up)
        """


class MockHealthChecker(HealthChecker):
    """Always reports healthy. Do not trust in production."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def check(self, branch_ids: list[str]) -> bool:
        return True
