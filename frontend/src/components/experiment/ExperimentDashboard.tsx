import { useMemo, useState } from "react";
import { useTrace } from "../../hooks/useTrace";
import { deriveExperiment } from "../../lib/experiment";
import type { CandidateState, ExperimentState, StreamStatus } from "../../types";
import { cn } from "../../lib/utils";
import { Alert, AlertDescription, AlertTitle } from "../ui/alert";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent } from "../ui/card";
import { Skeleton } from "../ui/skeleton";
import { CandidateCard } from "./CandidateCard";
import { Leaderboard } from "./Leaderboard";
import { SimpleDashboard } from "./SimpleDashboard";

const STATUS_LABEL: Record<StreamStatus, string> = {
  idle: "idle",
  connecting: "connecting",
  open: "racing",
  done: "complete",
  error: "stream error",
};

type View = "plain" | "technical";

export function ExperimentDashboard({
  traceId,
  onReset,
}: {
  traceId: string;
  onReset: () => void;
}) {
  const { events, status } = useTrace(traceId);
  const [view, setView] = useState<View>("plain");
  const exp = useMemo(() => deriveExperiment(events), [events]);
  const cands = useMemo(
    () => Object.values(exp.cands).sort((a, b) => a.index - b.index),
    [exp],
  );

  const hashes = cands.map((c) => c.worldHash).filter(Boolean);
  const identical = hashes.length > 0 && new Set(hashes).size === 1;
  const egressBlocked = cands.filter((c) => c.egressDenied > 0);

  if (!exp.taskTitle) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[220px] w-full" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-56" />
          <Skeleton className="h-56" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Badge className="border-emerald-800 text-emerald-300">
            <span
              className={`h-2 w-2 rounded-full ${
                status === "done" ? "bg-emerald-400" : "bg-emerald-400 animate-pulse"
              }`}
            />
            {STATUS_LABEL[status]}
          </Badge>
          <span className="text-sm font-medium text-zinc-200">{exp.taskTitle}</span>
          <span className="font-mono text-[11px] text-zinc-600">
            {exp.candidates} candidates · {exp.mode}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-900/60 p-1">
            {(["plain", "technical"] as View[]).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={cn(
                  "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                  view === v ? "bg-zinc-800 text-zinc-100" : "text-zinc-500 hover:text-zinc-300",
                )}
              >
                {v === "plain" ? "Plain English" : "Technical"}
              </button>
            ))}
          </div>
          <Button variant="outline" onClick={onReset}>
            New run
          </Button>
        </div>
      </div>

      {view === "plain" ? (
        <SimpleDashboard exp={exp} cands={cands} live={status !== "done"} />
      ) : (
        <TechnicalView
          exp={exp}
          cands={cands}
          hashes={hashes}
          identical={identical}
          egressBlocked={egressBlocked}
        />
      )}
    </div>
  );
}

function TechnicalView({
  exp,
  cands,
  hashes,
  identical,
  egressBlocked,
}: {
  exp: ExperimentState;
  cands: CandidateState[];
  hashes: (string | undefined)[];
  identical: boolean;
  egressBlocked: CandidateState[];
}) {
  return (
    <div className="space-y-4">

      {/* Reproducibility receipt — the copy-on-write "identical world" proof. */}
      {hashes.length > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-violet-900 bg-violet-950/30 px-3 py-2 text-xs text-violet-200">
          <span>🧬</span>
          <span>
            {hashes.length} sandboxes branched from an identical world{" "}
            <span className="font-mono text-violet-400">{exp.worldHash}</span>
            {identical ? " · verified identical ✓" : " · mismatch!"}
          </span>
          <span className="ml-auto text-violet-400/70">egress allowlist: {exp.allowlist.join(", ") || "—"}</span>
        </div>
      )}

      {egressBlocked.length > 0 && (
        <Alert variant="destructive">
          <AlertTitle>⛔ Egress blocked</AlertTitle>
          <AlertDescription>
            {egressBlocked
              .map((c) => `${c.label}: ${c.egressDenied} attempt(s) denied by egress policy`)
              .join(" · ")}
          </AlertDescription>
        </Alert>
      )}

      {cands.length > 0 ? (
        <Leaderboard cands={cands} winner={exp.winner} />
      ) : (
        <Card>
          <CardContent className="text-xs text-zinc-500">Warming candidates…</CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {cands.map((c) => (
          <CandidateCard key={c.index} c={c} winner={c.index === exp.winner} />
        ))}
      </div>
    </div>
  );
}
