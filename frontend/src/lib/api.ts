import type {
  ExperimentLaunchResponse,
  ExperimentRequest,
  LaunchRequest,
  LaunchResponse,
} from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function launchWorkspace(req: LaunchRequest): Promise<LaunchResponse> {
  const res = await fetch(`${API_URL}/v1/workspaces:launch`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`Launch failed (${res.status}): ${await res.text()}`);
  }
  return res.json();
}

export async function launchExperiment(
  req: ExperimentRequest,
): Promise<ExperimentLaunchResponse> {
  const res = await fetch(`${API_URL}/v1/experiments:launch`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`Launch failed (${res.status}): ${await res.text()}`);
  }
  return res.json();
}

export function traceStreamUrl(traceId: string): string {
  const wsBase = API_URL.replace(/^http/, "ws");
  return `${wsBase}/v1/traces/${traceId}/stream`;
}

/** Fire-and-forget early-intent signal so the control plane can start warming
 *  a shaped sandbox while the user is still composing the request. */
export function signalIntent(partial: Record<string, unknown> = {}): void {
  fetch(`${API_URL}/v1/intent:signal`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(partial),
  }).catch(() => {
    /* speculative — never surface an error for a hint */
  });
}

export interface PoolStats {
  enabled: boolean;
  size?: number;
  hits?: number;
  misses?: number;
  hit_rate?: number | null;
  warm?: { id: string; base_image: string; booted: boolean; age_seconds: number }[];
}

export async function fetchPoolStats(): Promise<PoolStats> {
  const res = await fetch(`${API_URL}/v1/pool`);
  if (!res.ok) return { enabled: false };
  return res.json();
}
