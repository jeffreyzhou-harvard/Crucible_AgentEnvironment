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
