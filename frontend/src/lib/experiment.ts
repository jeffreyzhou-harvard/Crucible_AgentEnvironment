import type { CandidateState, ExperimentState, TraceEvent, Verdict } from "../types";

const LOG_KINDS = new Set([
  "agent.start",
  "agent.message",
  "tool_call",
  "command_output",
  "egress.request",
  "secretless.check",
]);

function blankCandidate(index: number): CandidateState {
  return {
    index,
    label: `candidate-${index}`,
    role: "honest",
    log: [],
    status: "running",
    disqualified: false,
    egressDenied: 0,
  };
}

/** Fold the flat trace stream into per-candidate + experiment-level state. */
export function deriveExperiment(events: TraceEvent[]): ExperimentState {
  const state: ExperimentState = {
    candidates: 0,
    allowlist: [],
    winner: null,
    ended: false,
    cands: {},
  };

  const ensure = (i: number): CandidateState => {
    if (!state.cands[i]) state.cands[i] = blankCandidate(i);
    return state.cands[i];
  };

  for (const e of events) {
    const p = e.payload as Record<string, unknown>;

    if (e.kind === "experiment.start") {
      state.taskTitle = p.task_title as string;
      state.taskPrompt = p.task_prompt as string;
      state.candidates = (p.candidates as number) ?? 0;
      state.allowlist = (p.allowlist as string[]) ?? [];
      state.worldHash = p.world_hash as string;
      state.mode = p.mode as string;
      continue;
    }
    if (e.kind === "experiment.end") {
      state.ended = true;
      state.winner = (p.winner as number | null) ?? null;
      for (const row of (p.leaderboard as Record<string, unknown>[]) ?? []) {
        const c = ensure(row.candidate as number);
        c.status = (row.status as Verdict) ?? c.status;
        c.disqualified = (row.disqualified as boolean) ?? c.disqualified;
        if (c.heldOut === undefined) c.heldOut = row.held_out as number;
        if (c.inSandbox === undefined) c.inSandbox = row.in_sandbox as number;
      }
      continue;
    }

    const idx = p.candidate as number | undefined;
    if (idx === undefined) continue;
    const c = ensure(idx);

    switch (e.kind) {
      case "candidate.start":
        c.label = (p.label as string) ?? c.label;
        c.role = (p.role as string) ?? c.role;
        break;
      case "receipt":
        c.worldHash = p.world_hash as string;
        break;
      case "score":
        c.inSandbox = p.in_sandbox as number;
        c.heldOut = p.held_out as number;
        c.sampleTotal = p.sample_total as number;
        c.heldTotal = p.held_total as number;
        break;
      case "verdict":
        c.status = (p.status as Verdict) ?? c.status;
        c.disqualified = (p.disqualified as boolean) ?? c.disqualified;
        c.reason = p.reason as string;
        break;
      case "egress.request":
        if (p.decision === "denied") c.egressDenied += 1;
        break;
    }
    if (LOG_KINDS.has(e.kind)) c.log.push(e);
  }

  return state;
}

export function verdictClasses(status: Verdict): string {
  switch (status) {
    case "verified":
      return "border-emerald-700 bg-emerald-950/40 text-emerald-300";
    case "overfit":
      return "border-amber-700 bg-amber-950/40 text-amber-300";
    case "blocked":
    case "failed":
    case "error":
      return "border-rose-800 bg-rose-950/40 text-rose-300";
    default:
      return "border-sky-800 bg-sky-950/40 text-sky-300";
  }
}
