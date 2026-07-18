import type { LaunchRequest, LaunchResponse } from "../types";

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

export function traceStreamUrl(traceId: string): string {
  const wsBase = API_URL.replace(/^http/, "ws");
  return `${wsBase}/v1/traces/${traceId}/stream`;
}
