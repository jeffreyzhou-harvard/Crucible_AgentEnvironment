"""Trace durability tests: destroy the sandbox, keep the trajectory."""

from __future__ import annotations

from pathlib import Path

from agent_workspaces.config import Settings
from agent_workspaces.models import WorkspaceRequest
from agent_workspaces.trace.recorder import JsonlTraceRecorder


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        env="local",
        runtime_backend="mock",
        trace_store_uri=str(tmp_path / "traces"),
    )


async def test_trace_survives_process_restart(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    recorder = JsonlTraceRecorder(settings)
    request = WorkspaceRequest(agent_id="a", task_prompt="do the thing")

    trace_id = await recorder.start(workspace_id="ws_1", request=request)
    await recorder.finalize(trace_id)

    # Simulate a process restart: a brand-new recorder with no memory.
    reborn = JsonlTraceRecorder(settings)
    events = await reborn.load(trace_id)
    kinds = [e.kind for e in events]
    assert kinds[0] == "workspace.start"
    assert kinds[-1] == "workspace.end"
    assert events[0].payload["task_prompt"] == "do the thing"


async def test_unknown_trace_loads_empty(tmp_path: Path) -> None:
    recorder = JsonlTraceRecorder(_settings(tmp_path))
    assert await recorder.load("tr_nope") == []


async def test_file_uri_prefix_is_accepted(tmp_path: Path) -> None:
    settings = Settings(
        env="local",
        runtime_backend="mock",
        trace_store_uri=f"file://{tmp_path}/traces",
    )
    recorder = JsonlTraceRecorder(settings)
    trace_id = await recorder.start(
        workspace_id="ws_2", request=WorkspaceRequest(agent_id="a", task_prompt="t")
    )
    assert (Path(tmp_path) / "traces" / f"{trace_id}.jsonl").exists()
