"""Experiment dispatcher.

`run_experiment` picks the scripted path (no Docker / no API key — the reliable
demo) or the real Docker path based on settings, and guarantees the stream is
terminated with `experiment.end` even on failure.
"""

from __future__ import annotations

import uuid

from ..config import Settings
from ..models import ExperimentRequest, TraceId
from ..security.audit import EgressAuditLog
from ..trace.recorder import TraceRecorder
from ..trace.tracer import Tracer
from .scripted import run_scripted
from .tasks import get_task


def new_experiment_ids() -> tuple[str, TraceId]:
    token = uuid.uuid4().hex[:12]
    return f"exp_{token}", f"tr_{token}"


def _is_scripted(settings: Settings) -> bool:
    # Scripted unless the operator explicitly opted into the real Docker path.
    return settings.experiment_scripted or settings.runtime_backend != "docker"


async def run_experiment(
    recorder: TraceRecorder,
    settings: Settings,
    request: ExperimentRequest,
    experiment_id: str,
    trace_id: TraceId,
    audit: EgressAuditLog | None = None,
) -> None:
    task = get_task(request.task_id)
    n = request.candidates or settings.experiment_candidates
    redteam = request.redteam if request.redteam is not None else settings.experiment_redteam
    redteam = max(0, min(redteam, n))
    rounds = request.rounds if request.rounds is not None else settings.experiment_rounds
    rounds = max(1, min(rounds, 10))
    allowlist = settings.egress_hosts or ["github.com", "pypi.org"]

    try:
        if _is_scripted(settings):
            await run_scripted(
                recorder, trace_id, experiment_id, task, n, redteam, rounds, allowlist,
                audit=audit, step_delay=settings.experiment_step_delay,
            )
        else:
            from .docker_runner import run_docker

            await run_docker(
                recorder, trace_id, experiment_id, task, n, redteam, rounds, allowlist, settings,
                audit=audit,
            )
    except Exception as exc:  # noqa: BLE001 — surface and still terminate the stream
        exp = Tracer(recorder, trace_id, experiment_id)
        await exp.emit("error", message=f"{type(exc).__name__}: {exc}")
        await exp.emit("experiment.end", leaderboard=[], winner=None, progression=[])
