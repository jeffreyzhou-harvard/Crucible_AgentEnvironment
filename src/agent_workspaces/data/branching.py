"""Database branching — copy-on-write off a shared read-only snapshot.

The reproducibility trick: every run reads from the *same* reference snapshot but
writes into a *private* delta. Two runs can hammer the same 200 GB database
simultaneously, each seeing an identical starting state, with only their own
changes stored. Branch creation is near-instant and near-free.
"""

from __future__ import annotations

import abc
import asyncio
import hashlib
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from ..config import Settings
from ..models import DataBranch, SnapshotId


class BranchingBackend(abc.ABC):
    """Creates and discards copy-on-write branches of a reference snapshot."""

    @abc.abstractmethod
    async def create_branch(self, snapshot_id: SnapshotId | str, label: str) -> DataBranch:
        """Create a writable branch off `snapshot_id`; return the branch handle.

        Must be O(1)-ish regardless of dataset size — that's the whole point.
        The returned `DataBranch` carries connection/attachment info (path) and
        the content-hash receipt proving the starting state.
        """

    @abc.abstractmethod
    async def discard_branch(self, branch: DataBranch) -> None:
        """Drop a branch and its delta. The reference snapshot is never modified."""


class MockBranchingBackend(BranchingBackend):
    """Hands out fake branch ids. Stores no data."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def create_branch(self, snapshot_id: SnapshotId | str, label: str) -> DataBranch:
        return DataBranch(id=f"branch_{uuid.uuid4().hex[:10]}")

    async def discard_branch(self, branch: DataBranch) -> None:
        return None


def _hash_tree(root: Path) -> str:
    """Deterministic content hash of a file or directory tree.

    Hashes relative paths + bytes in sorted order, so two branches hash equal
    iff their starting content is byte-identical. This is the "same world"
    receipt the frontend shows for every run.
    """
    digest = hashlib.sha256()
    if root.is_file():
        digest.update(root.name.encode())
        digest.update(root.read_bytes())
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _cow_copy(src: Path, dst: Path) -> None:
    """Copy `src` to `dst` using the filesystem's copy-on-write primitive.

    - macOS/APFS: `cp -c` (clonefile) — instant, shares blocks until written
    - Linux/Btrfs/XFS: `cp --reflink=auto` — same trick via reflinks
    - anywhere else: falls back to a regular copy (correct, just not O(1))

    Either way the branch starts byte-identical to the snapshot and private
    writes never touch the reference.
    """
    if sys.platform == "darwin":
        cmd = ["cp", "-Rc", str(src), str(dst)]
    else:
        cmd = ["cp", "-R", "--reflink=auto", str(src), str(dst)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # CoW unsupported on this filesystem — fall back to a plain copy.
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


class CowBranchingBackend(BranchingBackend):
    """Real copy-on-write branching for filesystem-backed datasets.

    Branches `settings.dataset_snapshot_uri` (a local file or directory — e.g.
    a SQLite db, a Parquet directory, a fixtures tree) into a private per-run
    path using APFS clonefile / Linux reflink. Creation cost is O(metadata),
    not O(bytes), and each branch's content hash is recorded so identical
    starting worlds are *provable*, not asserted.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._root = Path(settings.data_branch_dir).expanduser()
        self._branches: dict[str, Path] = {}
        self._snapshot_hashes: dict[str, str] = {}  # snapshot path -> reference hash

    async def create_branch(self, snapshot_id: SnapshotId | str, label: str) -> DataBranch:
        snapshot = Path(str(snapshot_id)).expanduser()  # noqa: ASYNC240 — pure path math, no I/O
        branch_id = f"branch_{uuid.uuid4().hex[:10]}"
        dst = self._root / branch_id / snapshot.name

        def _create() -> str:
            if not snapshot.exists():
                raise FileNotFoundError(f"reference snapshot not found: {snapshot}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            _cow_copy(snapshot, dst)
            return _hash_tree(dst)

        content_hash = await asyncio.to_thread(_create)
        self._branches[branch_id] = dst
        return DataBranch(
            id=branch_id, path=str(dst), source=str(snapshot), content_hash=content_hash
        )

    async def discard_branch(self, branch: DataBranch) -> None:
        path = self._branches.pop(branch.id, None)
        if path is None and branch.path:
            path = Path(branch.path)
        if path is None:
            return
        await asyncio.to_thread(shutil.rmtree, path.parent, ignore_errors=True)

    async def reference_hash(self, snapshot_id: SnapshotId | str) -> str:
        """Content hash of the reference snapshot itself (cached).

        The health checker compares each branch against this to *prove* the
        branch starts identical to the reference.
        """
        key = str(Path(str(snapshot_id)).expanduser())  # noqa: ASYNC240 — pure path math, no I/O
        if key not in self._snapshot_hashes:
            self._snapshot_hashes[key] = await asyncio.to_thread(_hash_tree, Path(key))
        return self._snapshot_hashes[key]
