"""DataPlane — the data plane's public interface.

Provisions the datasets a request asks for (PostgreSQL, Redis, analytical stores)
by branching them from a shared read-only snapshot, then tears the branches down.
"""

from __future__ import annotations

import abc

from ..config import Settings
from ..models import DataBranch, DatasetSpec, Sandbox
from .branching import BranchingBackend, CowBranchingBackend, MockBranchingBackend
from .health import CowHealthChecker, HealthChecker, MockHealthChecker


class DataPlaneError(RuntimeError):
    """The data plane could not provision a reproducible starting state.

    Raised so the orchestrator can release the sandbox and fail the run cleanly,
    rather than letting the agent run against missing or unhealthy data.
    """


class DataPlane(abc.ABC):
    """Makes datasets available to a sandbox and reclaims them afterwards."""

    @abc.abstractmethod
    async def branch(self, sandbox: Sandbox, datasets: list[DatasetSpec]) -> list[DataBranch]:
        """Create per-run branches for `datasets`; return their handles.

        Each branch shares read-only reference data and keeps private writes as a
        delta, so every run starts identical with near-zero storage overhead.
        """

    @abc.abstractmethod
    async def teardown(self, branches: list[DataBranch]) -> None:
        """Discard the run's branches (deltas dropped; reference untouched)."""


class StandardDataPlane(DataPlane):
    """Branch + health-check pipeline over a pluggable backend.

    With the mock backend this provisions nothing real (fake ids, always
    healthy). With the CoW backend it materializes real copy-on-write branches
    and *proves* each one starts identical to the reference snapshot.
    """

    #: When True, a requested dataset with no configured snapshot is an error —
    #: silently starting from empty data destroys reproducibility.
    strict = False

    def __init__(
        self,
        settings: Settings,
        backend: BranchingBackend | None = None,
        health: HealthChecker | None = None,
    ) -> None:
        self.settings = settings
        self.backend = backend or MockBranchingBackend(settings)
        self.health = health or MockHealthChecker(settings)

    async def branch(self, sandbox: Sandbox, datasets: list[DatasetSpec]) -> list[DataBranch]:
        branches: list[DataBranch] = []
        try:
            for ds in datasets:
                snapshot = ds.snapshot_id or self.settings.dataset_snapshot_uri
                if not snapshot:
                    if self.strict:
                        raise DataPlaneError(
                            f"dataset {ds.name!r} requested but no snapshot is configured "
                            "(set AWS_DATASET_SNAPSHOT_URI or DatasetSpec.snapshot_id)"
                        )
                    # Mock mode stays lenient so the zero-infra demo path works.
                branch = await self.backend.create_branch(
                    snapshot_id=snapshot, label=f"{sandbox.id}:{ds.name}"
                )
                branch.dataset = ds.name
                branch.kind = ds.kind
                branches.append(branch)
        except DataPlaneError:
            await self.teardown(branches)
            raise
        except Exception as exc:
            await self.teardown(branches)
            raise DataPlaneError(f"branching failed: {exc}") from exc

        # Health-check BEFORE the agent is allowed to touch the data. On failure,
        # discard the branches and raise so the orchestrator releases the sandbox
        # instead of running blind against unhealthy data.
        healthy = await self.health.check(branches)
        if not healthy:
            await self.teardown(branches)
            raise DataPlaneError("data plane health check failed")
        return branches

    async def teardown(self, branches: list[DataBranch]) -> None:
        for branch in branches:
            await self.backend.discard_branch(branch)


class MockDataPlane(StandardDataPlane):
    """Wires the mock branching backend + health checker. Provisions nothing real."""

    strict = False


class CowDataPlane(StandardDataPlane):
    """Real data plane: filesystem copy-on-write branches with hash receipts."""

    strict = True

    def __init__(self, settings: Settings) -> None:
        backend = CowBranchingBackend(settings)
        super().__init__(settings, backend=backend, health=CowHealthChecker(settings, backend))
