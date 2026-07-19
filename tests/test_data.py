"""Data plane tests: real copy-on-write branches with provable identical starts."""

# ruff: noqa: ASYNC240 — direct Path I/O in async tests is fine; nothing else runs.
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from agent_workspaces.config import Settings
from agent_workspaces.data.branching import CowBranchingBackend
from agent_workspaces.data.provisioner import CowDataPlane, DataPlaneError
from agent_workspaces.models import DatasetSpec, Sandbox, SandboxState


def _sandbox() -> Sandbox:
    return Sandbox(
        id="sbx_test",
        state=SandboxState.CLAIMED,
        base_image="python:3.11",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def snapshot(tmp_path: Path) -> Path:
    ref = tmp_path / "snapshot"
    ref.mkdir()
    (ref / "users.csv").write_text("id,name\n1,ada\n2,grace\n")
    (ref / "nested").mkdir()
    (ref / "nested" / "orders.csv").write_text("id,total\n1,99\n")
    return ref


@pytest.fixture
def settings(tmp_path: Path, snapshot: Path) -> Settings:
    return Settings(
        env="local",
        runtime_backend="mock",
        data_branch_backend="cow",
        dataset_snapshot_uri=str(snapshot),
        data_branch_dir=str(tmp_path / "branches"),
    )


async def test_branches_start_identical_and_writes_stay_private(
    settings: Settings, snapshot: Path
) -> None:
    plane = CowDataPlane(settings)
    a = await plane.branch(_sandbox(), [DatasetSpec(name="db", kind="analytical")])
    b = await plane.branch(_sandbox(), [DatasetSpec(name="db", kind="analytical")])

    # The reproducibility receipt: both branches hash identical to each other
    # (and, per the health check, to the reference snapshot).
    assert a[0].content_hash == b[0].content_hash
    assert a[0].path != b[0].path

    # Private delta: mutating branch A touches neither the reference nor branch B.
    assert a[0].path is not None and b[0].path is not None
    (Path(a[0].path) / "users.csv").write_text("id,name\n1,TAMPERED\n")
    assert (snapshot / "users.csv").read_text().count("TAMPERED") == 0
    assert (Path(b[0].path) / "users.csv").read_text().count("TAMPERED") == 0

    await plane.teardown(a)
    await plane.teardown(b)
    assert not Path(a[0].path).exists()


async def test_missing_snapshot_fails_loudly(tmp_path: Path) -> None:
    plane = CowDataPlane(
        Settings(
            env="local",
            runtime_backend="mock",
            data_branch_backend="cow",
            dataset_snapshot_uri="",  # nothing configured
            data_branch_dir=str(tmp_path / "branches"),
        )
    )
    # Silently starting from empty data destroys reproducibility — refuse.
    with pytest.raises(DataPlaneError, match="no snapshot"):
        await plane.branch(_sandbox(), [DatasetSpec(name="db", kind="postgres")])


async def test_nonexistent_snapshot_path_fails_loudly(tmp_path: Path) -> None:
    plane = CowDataPlane(
        Settings(
            env="local",
            runtime_backend="mock",
            data_branch_backend="cow",
            dataset_snapshot_uri=str(tmp_path / "does-not-exist"),
            data_branch_dir=str(tmp_path / "branches"),
        )
    )
    with pytest.raises(DataPlaneError):
        await plane.branch(_sandbox(), [DatasetSpec(name="db", kind="postgres")])


async def test_health_check_catches_receipt_mismatch(settings: Settings) -> None:
    plane = CowDataPlane(settings)
    backend = plane.backend
    assert isinstance(backend, CowBranchingBackend)

    branch = await backend.create_branch(settings.dataset_snapshot_uri, "x")
    branch.content_hash = "0" * 64  # simulate a torn/corrupted copy
    assert await plane.health.check([branch]) is False

    good = await backend.create_branch(settings.dataset_snapshot_uri, "y")
    assert await plane.health.check([good]) is True


async def test_single_file_snapshot_branches(tmp_path: Path) -> None:
    db = tmp_path / "app.sqlite"
    db.write_bytes(b"sqlite-ish bytes")
    plane = CowDataPlane(
        Settings(
            env="local",
            runtime_backend="mock",
            data_branch_backend="cow",
            dataset_snapshot_uri=str(db),
            data_branch_dir=str(tmp_path / "branches"),
        )
    )
    branches = await plane.branch(_sandbox(), [DatasetSpec(name="app", kind="sqlite")])
    assert branches[0].path is not None
    assert Path(branches[0].path).read_bytes() == b"sqlite-ish bytes"
    await plane.teardown(branches)
