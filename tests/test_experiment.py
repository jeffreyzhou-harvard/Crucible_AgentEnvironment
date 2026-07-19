"""Scripted best-of-N experiment: event-stream shape + anti-gaming semantics."""

from __future__ import annotations

from agent_workspaces.config import Settings
from agent_workspaces.experiment.runner import new_experiment_ids, run_experiment
from agent_workspaces.models import ExperimentRequest
from agent_workspaces.security.audit import EgressAuditLog
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

    # The red-team candidate's egress attempt is denied — using the unified
    # `security.egress` event shared with the single-run security plane.
    assert any(
        e.kind == "security.egress" and e.payload.get("allowed") is False for e in events
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


async def test_experiment_denials_land_in_the_shared_security_audit() -> None:
    """The experiment records egress denials into the SAME audit log the security
    plane exposes via GET /v1/security/egress-audit — one audit trail, not two."""
    settings = _settings()
    recorder = InMemoryTraceRecorder(settings=settings, bus=TraceBus())
    audit = EgressAuditLog()
    exp_id, trace_id = new_experiment_ids()

    await run_experiment(
        recorder,
        settings,
        ExperimentRequest(candidates=4, redteam=1),
        exp_id,
        trace_id,
        audit=audit,
    )
    entries = audit.entries()
    assert any(e["allowed"] is False and e["host"] == "pastebin.com" for e in entries)


async def test_scripted_narration_is_task_aware() -> None:
    """The scripted path must narrate the SELECTED task, not a hardcoded story: the
    adversarial `sequence` task reads its planted answer file and its red-team probe is
    blocked on the exact URL planted in hints.md (not the devowel pastebin URL)."""
    settings = _settings()
    recorder = InMemoryTraceRecorder(settings=settings, bus=TraceBus())
    exp_id, trace_id = new_experiment_ids()

    await run_experiment(
        recorder,
        settings,
        ExperimentRequest(task_id="sequence", candidates=4, redteam=1),
        exp_id,
        trace_id,
    )
    events = await recorder.load(trace_id)
    commands = [e.payload["command"] for e in events if e.kind == "tool_call"]
    egress_hosts = {
        e.payload.get("host") for e in events if e.kind == "security.egress"
    }

    assert any("3*n*(n-1)+1" in c for c in commands)  # honest closed-form, not vowels
    assert any("data/known_terms.json" in c for c in commands)  # reads the planted file
    assert egress_hosts == {"oeis-mirror.internal"}  # blocked on the planted URL's host


async def test_self_improvement_loop_climbs_across_rounds() -> None:
    """A multi-round experiment seeds each round from the previous winner; the best
    held-out score must be non-decreasing and end strictly higher than it started."""
    settings = _settings()
    recorder = InMemoryTraceRecorder(settings=settings, bus=TraceBus())
    exp_id, trace_id = new_experiment_ids()

    await run_experiment(
        recorder,
        settings,
        ExperimentRequest(task_id="sequence", candidates=4, redteam=1, rounds=3),
        exp_id,
        trace_id,
    )
    events = await recorder.load(trace_id)
    kinds = [e.kind for e in events]

    # One round.start / round.end per round, still terminated by experiment.end.
    assert kinds.count("round.start") == 3
    assert kinds.count("round.end") == 3
    assert kinds[-1] == "experiment.end"

    end = events[-1].payload
    progression = end["progression"]
    bests = [p["best_held_out"] for p in progression]
    assert len(bests) == 3
    assert bests == sorted(bests)  # non-decreasing: the loop never regresses
    assert bests[-1] > bests[0]  # and it actually improved

    # The overall winner comes from a later round (a higher global candidate index).
    assert end["winner"] is not None
    assert end["winner"] >= 4  # round 0 uses indices 0..3; a later round won

    # Every candidate event is stamped with its round so the UI can group by generation.
    receipts = [e for e in events if e.kind == "receipt"]
    assert len(receipts) == 12  # 4 candidates × 3 rounds
    assert {e.payload["round"] for e in receipts} == {0, 1, 2}


async def test_candidates_emit_their_solution_code() -> None:
    """Each candidate surfaces the code it wrote: an overfitter's is a hardcoded lookup
    of the sample answers, an honest candidate's is real general logic. The dashboard
    diffs these to make cheating visible."""
    settings = _settings()
    recorder = InMemoryTraceRecorder(settings=settings, bus=TraceBus())
    exp_id, trace_id = new_experiment_ids()

    await run_experiment(
        recorder, settings, ExperimentRequest(candidates=4, redteam=1), exp_id, trace_id
    )
    events = await recorder.load(trace_id)
    sols = {e.payload["candidate"]: e.payload["code"] for e in events if e.kind == "solution"}
    verdicts = {e.payload["candidate"]: e.payload["status"] for e in events if e.kind == "verdict"}

    assert len(sols) == 4  # every candidate emits one
    # The overfitter/red-team hardcodes a lookup; the verified winner does not.
    cheats = [sols[i] for i, v in verdicts.items() if v in ("overfit", "blocked")]
    honest = [sols[i] for i, v in verdicts.items() if v == "verified"]
    assert cheats and all(".get(" in s for s in cheats)
    assert honest and all(".get(" not in s for s in honest)


async def test_single_round_default_is_backward_compatible() -> None:
    """Default request (no rounds) behaves like the original single best-of-N run."""
    settings = _settings()
    recorder = InMemoryTraceRecorder(settings=settings, bus=TraceBus())
    exp_id, trace_id = new_experiment_ids()

    await run_experiment(
        recorder, settings, ExperimentRequest(candidates=4, redteam=1), exp_id, trace_id
    )
    events = await recorder.load(trace_id)
    kinds = [e.kind for e in events]

    assert kinds.count("round.start") == 1
    assert kinds[-1] == "experiment.end"
    assert len([e for e in events if e.kind == "receipt"]) == 4
