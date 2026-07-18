import { useState } from "react";
import { LaunchForm } from "./components/LaunchForm";
import { WorkspaceView } from "./components/WorkspaceView";
import type { LaunchResponse } from "./types";

export default function App() {
  const [run, setRun] = useState<LaunchResponse | null>(null);

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col px-6 py-6">
      <header className="mb-6 flex items-baseline justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-zinc-100">
            Agent Workspaces
          </h1>
          <p className="text-xs text-zinc-500">
            Mission control — watch an agent work inside an isolated, reproducible sandbox.
          </p>
        </div>
        <a
          href="https://neosigma.ai/blog/agent-workspaces"
          target="_blank"
          rel="noreferrer"
          className="text-xs text-zinc-600 hover:text-zinc-400"
        >
          concept ↗
        </a>
      </header>

      <main className="min-h-0 flex-1">
        {run ? (
          <WorkspaceView
            workspaceId={run.workspace_id}
            traceId={run.trace_id}
            onReset={() => setRun(null)}
          />
        ) : (
          <LaunchForm onLaunched={setRun} />
        )}
      </main>
    </div>
  );
}
