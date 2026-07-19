"""Health checks — prove the data is ready before the agent gets the sandbox.

Handing an agent a database that's still restoring, or a branch that came up empty,
produces failures that look like agent bugs. Gate handoff on a health check so a
green sandbox always means a genuinely ready environment.
"""

from __future__ import annotations

import abc
import asyncio
from pathlib import Path

from ..config import Settings
from ..models import DataBranch
from .branching import CowBranchingBackend


class HealthChecker(abc.ABC):
    """Verifies provisioned data branches are ready and correct."""

    @abc.abstractmethod
    async def check(self, branches: list[DataBranch]) -> bool:
        """Return True only if every branch is reachable and passes its checks."""


class MockHealthChecker(HealthChecker):
    """Always reports healthy. Do not trust in production."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def check(self, branches: list[DataBranch]) -> bool:
        return True


class CowHealthChecker(HealthChecker):
    """Proves each CoW branch starts *identical* to its reference snapshot.

    Three checks per branch, with bounded retries (a branch may still be
    materializing on a slow filesystem):
      1. the branch path exists and is reachable
      2. the branch carries a content-hash receipt
      3. the receipt equals the reference snapshot's own hash — the
         cryptographic "same starting world" guarantee, not a vibe
    """

    RETRIES = 3
    RETRY_DELAY = 0.2

    def __init__(self, settings: Settings, backend: CowBranchingBackend) -> None:
        self.settings = settings
        self.backend = backend

    async def check(self, branches: list[DataBranch]) -> bool:
        for branch in branches:
            if not await self._check_one(branch):
                return False
        return True

    async def _check_one(self, branch: DataBranch) -> bool:
        for attempt in range(self.RETRIES):
            exists = branch.path is not None and await asyncio.to_thread(
                Path(branch.path).exists
            )
            if exists and branch.content_hash:
                if branch.source is None:
                    return False
                reference = await self.backend.reference_hash(branch.source)
                return branch.content_hash == reference
            if attempt < self.RETRIES - 1:
                await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
        return False
