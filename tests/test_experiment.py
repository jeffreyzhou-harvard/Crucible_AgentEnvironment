"""Scripted best-of-N experiment: event-stream shape + anti-gaming semantics."""

from __future__ import annotations

from agent_workspaces.config import Settings
from agent_workspaces.experiment.runner import new_experiment_ids, run_experiment
from agent_workspaces.models import ExperimentRequest
from agent_workspaces.trace.bus import TraceBus
from agent_workspaces.trace.recorder import InMemoryTraceRecorder


def _settings() -> Settings:
    # runtime_backend != docker → scripted path; zero delay so the test is fast.
    return Settings(runtime_backend="mock", experiment_step_delay=0.0)


async def test_scripted_experiment_stream_shape() -> None:
    settings = _settings()
    recorder = InMemoryTraceRecorder(settings=settings, bus=TraceBus())
    exp_id, trace_id = new_experiment_ids()

    await run_experiment(
        recorder, settings, ExperimentRequest(candidates=4, redteam=1), exp_id, trace_id
    )
    events = await recorder.load(trace_id)
    kinds = [e.kind for e in events]

    assert kinds[0] == "experiment.start"
    assert kinds[-1] == "experiment.end"
    assert "score" in kinds and "verdict" in kinds

    # Every candidate event is stamped so the frontend can demux into columns.
    receipts = [e for e in events if e.kind == "receipt"]
    assert len(receipts) == 4
    assert all("candidate" in e.payload for e in receipts)
    # Reproducibility receipt: all candidates start from an identical world.
    assert len({e.payload["world_hash"] for e in receipts}) == 1


async def test_held_out_grader_exposes_gaming_and_blocks_egress() -> None:
    settings = _settings()
    recorder = InMemoryTraceRecorder(settings=settings, bus=TraceBus())
    exp_id, trace_id = new_experiment_ids()

    await run_experiment(
        recorder, settings, ExperimentRequest(candidates=4, redteam=1), exp_id, trace_id
    )
    events = await recorder.load(trace_id)

    # The red-team candidate's egress attempt is denied.
    assert any(
        e.kind == "egress.request" and e.payload.get("decision") == "denied" for e in events
    )

    # The two-number score exposes an overfitter: high in-sandbox, low held-out.
    scores = [e.payload for e in events if e.kind == "score"]
    assert any(
        s["in_sandbox"] == s["sample_total"] and s["held_out"] < s["held_total"] for s in scores
    )

    # A verified winner exists and is not disqualified.
    end = events[-1].payload
    assert end["winner"] is not None
    board = {row["candidate"]: row for row in end["leaderboard"]}
    assert board[end["winner"]]["disqualified"] is False
