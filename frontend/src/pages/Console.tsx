import { useState } from "react";
import { Link } from "react-router-dom";
import { LaunchForm } from "../components/LaunchForm";
import { WorkspaceView } from "../components/WorkspaceView";
import { ExperimentLauncher } from "../components/experiment/ExperimentLauncher";
import { ExperimentDashboard } from "../components/experiment/ExperimentDashboard";
import { cn } from "../lib/utils";
import type { ExperimentLaunchResponse, LaunchResponse } from "../types";

type Mode = "experiment" | "single";

export default function Console() {
  const [mode, setMode] = useState<Mode>("experiment");
  const [run, setRun] = useState<LaunchResponse | null>(null);
  const [exp, setExp] = useState<ExperimentLaunchResponse | null>(null);

  function reset() {
    setRun(null);
    setExp(null);
  }

  function switchMode(next: Mode) {
    reset();
    setMode(next);
  }

  const tab = (m: Mode, label: string) => (
    <button
      onClick={() => switchMode(m)}
      className={cn(
        "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
        mode === m ? "bg-zinc-800 text-zinc-100" : "text-zinc-500 hover:text-zinc-300",
      )}
    >
      {label}
    </button>
  );

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col px-6 py-6">
      <header className="mb-6 flex items-center justify-between">
        <Link to="/" className="group">
          <h1 className="text-lg font-semibold tracking-tight text-zinc-100">
            <span className="text-emerald-400">◆</span> Agent Workspaces
          </h1>
          <p className="text-xs text-zinc-500 group-hover:text-zinc-400">← back to home</p>
        </Link>
        <div className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 p-1">
          {tab("experiment", "Best-of-N")}
          {tab("single", "Single run")}
        </div>
      </header>

      <main className="min-h-0 flex-1">
        {mode === "experiment" ? (
          exp ? (
            <ExperimentDashboard traceId={exp.trace_id} onReset={reset} />
          ) : (
            <ExperimentLauncher onLaunched={setExp} />
          )
        ) : run ? (
          <WorkspaceView workspaceId={run.workspace_id} traceId={run.trace_id} onReset={reset} />
        ) : (
          <LaunchForm onLaunched={setRun} />
        )}
      </main>
    </div>
  );
}
