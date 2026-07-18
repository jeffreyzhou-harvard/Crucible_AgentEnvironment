"""Database branching — copy-on-write off a shared read-only snapshot.

The reproducibility trick: every run reads from the *same* reference snapshot but
writes into a *private* delta. Two runs can hammer the same 200 GB database
simultaneously, each seeing an identical starting state, with only their own
changes stored. Branch creation is near-instant and near-free.
"""

from __future__ import annotations

import abc
import uuid

from ..config import Settings
from ..models import SnapshotId


class BranchingBackend(abc.ABC):
    """Creates and discards copy-on-write branches of a reference snapshot."""

    @abc.abstractmethod
    async def create_branch(self, snapshot_id: SnapshotId | str, label: str) -> str:
        """Create a writable branch off `snapshot_id`; return the branch id.

        Must be O(1)-ish regardless of dataset size — that's the whole point.

        TODO: implement against a real CoW mechanism, e.g.:
          - Neon / Postgres branching for relational data
          - ZFS/Btrfs snapshots for filesystem-backed stores
          - Redis RDB fork-and-load for caches
        Return connection info the sandbox can use (coordinate with the provisioner).
        """

    @abc.abstractmethod
    async def discard_branch(self, branch_id: str) -> None:
        """Drop a branch and its delta. The reference snapshot is never modified."""


class MockBranchingBackend(BranchingBackend):
    """Hands out fake branch ids. Stores no data."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def create_branch(self, snapshot_id: SnapshotId | str, label: str) -> str:
        return f"branch_{uuid.uuid4().hex[:10]}"

    async def discard_branch(self, branch_id: str) -> None:
        return None
