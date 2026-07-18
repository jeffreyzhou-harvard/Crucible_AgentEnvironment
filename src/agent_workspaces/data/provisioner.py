"""DataPlane — the data plane's public interface.

Provisions the datasets a request asks for (PostgreSQL, Redis, analytical stores)
by branching them from a shared read-only snapshot, then tears the branches down.
"""

from __future__ import annotations

import abc

from ..config import Settings
from ..models import DatasetSpec, Sandbox
from .branching import BranchingBackend, MockBranchingBackend
from .health import HealthChecker, MockHealthChecker


class DataPlaneError(RuntimeError):
    """The data plane could not provision a reproducible starting state.

    Raised so the orchestrator can release the sandbox and fail the run cleanly,
    rather than letting the agent run against missing or unhealthy data.
    """


class DataPlane(abc.ABC):
    """Makes datasets available to a sandbox and reclaims them afterwards."""

    @abc.abstractmethod
    async def branch(self, sandbox: Sandbox, datasets: list[DatasetSpec]) -> list[str]:
        """Create per-run branches for `datasets`; return their branch ids.

        Each branch shares read-only reference data and keeps private writes as a
        delta, so every run starts identical with near-zero storage overhead.
        """

    @abc.abstractmethod
    async def teardown(self, branch_ids: list[str]) -> None:
        """Discard the run's branches (deltas dropped; reference untouched)."""


class MockDataPlane(DataPlane):
    """Wires the mock branching backend + health checker. Provisions nothing real."""

    def __init__(
        self,
        settings: Settings,
        backend: BranchingBackend | None = None,
        health: HealthChecker | None = None,
    ) -> None:
        self.settings = settings
        self.backend = backend or MockBranchingBackend(settings)
        self.health = health or MockHealthChecker(settings)

    async def branch(self, sandbox: Sandbox, datasets: list[DatasetSpec]) -> list[str]:
        branch_ids: list[str] = []
        for ds in datasets:
            snapshot = ds.snapshot_id or self.settings.dataset_snapshot_uri
            # TODO: fail loudly if no snapshot is configured for a requested dataset —
            #       silently starting from empty data destroys reproducibility.
            branch_id = await self.backend.create_branch(
                snapshot_id=snapshot, label=f"{sandbox.id}:{ds.name}"
            )
            # TODO: attach the branch's connection info into the sandbox (env/secret
            #       file) VIA the execution plane — coordinate ordering with attach().
            branch_ids.append(branch_id)

        # Health-check BEFORE the agent is allowed to touch the data. On failure,
        # discard the branches and raise so the orchestrator releases the sandbox
        # instead of running blind against unhealthy data.
        healthy = await self.health.check(branch_ids)
        if not healthy:
            await self.teardown(branch_ids)
            raise DataPlaneError("data plane health check failed")
        return branch_ids

    async def teardown(self, branch_ids: list[str]) -> None:
        for branch_id in branch_ids:
            await self.backend.discard_branch(branch_id)
