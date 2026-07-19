// Mirrors agent_workspaces.models. Keep in sync with the backend.

export interface TraceEvent {
  trace_id: string;
  ts: string;
  kind: string;
  payload: Record<string, unknown>;
}

export interface RepoSpec {
  url: string;
  ref: string;
}

export interface LaunchRequest {
  agent_id: string;
  task_prompt: string;
  repos: RepoSpec[];
  datasets: { name: string; kind: string }[];
  extra_egress_hosts: string[];
}

export interface LaunchResponse {
  workspace_id: string;
  trace_id: string;
}

export type StreamStatus = "idle" | "connecting" | "open" | "done" | "error";

export interface ExperimentRequest {
  task_id: string;
  candidates: number;
  redteam?: number;
  rounds?: number;
}

export interface ExperimentLaunchResponse {
  experiment_id: string;
  trace_id: string;
}

export type Verdict = "verified" | "overfit" | "blocked" | "failed" | "error" | "running";

export interface CandidateState {
  index: number;
  round: number;
  label: string;
  role: "honest" | "redteam" | string;
  worldHash?: string;
  log: TraceEvent[];
  inSandbox?: number;
  heldOut?: number;
  sampleTotal?: number;
  heldTotal?: number;
  status: Verdict;
  disqualified: boolean;
  reason?: string;
  egressDenied: number;
  solution?: string;
}

export interface RoundPoint {
  round: number;
  bestHeldOut: number;
  heldTotal: number;
}

export interface ExperimentState {
  taskTitle?: string;
  taskPrompt?: string;
  candidates: number;
  rounds: number;
  allowlist: string[];
  worldHash?: string;
  mode?: string;
  winner: number | null;
  ended: boolean;
  progression: RoundPoint[];
  cands: Record<number, CandidateState>;
}
