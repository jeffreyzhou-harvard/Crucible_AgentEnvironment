import { useEffect, useRef, useState } from "react";
import { verdictClasses } from "../../lib/experiment";
import type { CandidateState, TraceEvent } from "../../types";
import { Badge } from "../ui/badge";
import { Card } from "../ui/card";
import { cn } from "../../lib/utils";

function s(v: unknown): string {
  return typeof v === "string" ? v : v == null ? "" : String(v);
}

function LogLine({ event }: { event: TraceEvent }) {
  const p = event.payload;
  switch (event.kind) {
    case "agent.start":
      return <div className="text-zinc-600">▸ agent online</div>;
    case "agent.message":
      return <div className="whitespace-pre-wrap text-zinc-400">{s(p.text)}</div>;
    case "tool_call":
      return (
        <div className="text-emerald-400">
          <span className="text-emerald-600">$</span> {s(p.command)}
        </div>
      );
    case "command_output": {
      const failed = typeof p.exit_code === "number" && p.exit_code !== 0;
      return (
        <div className={cn("whitespace-pre-wrap pl-2", failed ? "text-rose-400/80" : "text-zinc-500")}>
          {s(p.output)}
        </div>
      );
    }
    case "security.egress":
      return p.allowed === false ? (
        <div className="text-rose-400">⛔ egress BLOCK · {s(p.host)} · {s(p.reason)}</div>
      ) : (
        <div className="text-zinc-500">
          ⇅ egress ALLOW · {s(p.host)}
          {p.credential_injected === true ? " · credential injected" : ""}
        </div>
      );
    case "secretless.check":
      return <div className="text-amber-400">🔒 secretless · {s(p.sample)}</div>;
    default:
      return null;
  }
}

// Sandbox lifecycle, derived from the trace: boot → solve → grade → verdict.
type Phase = { label: string; state: "done" | "active" | "todo" };

function phases(c: CandidateState): Phase[] {
  const booted = Boolean(c.worldHash) || c.log.length > 0;
  const solving = c.log.some((e) => e.kind === "tool_call");
  const scored = c.inSandbox !== undefined || c.heldOut !== undefined;
  const decided = c.status !== "running";
  const mk = (label: string, done: boolean, active: boolean): Phase => ({
    label,
    state: done ? "done" : active ? "active" : "todo",
  });
  return [
    mk("boot", booted, !booted),
    mk("solve", scored || decided, booted && !scored && !decided && solving),
    mk("grade", decided, scored && !decided),
    mk("verdict", decided, false),
  ];
}

function PhaseTracker({ c }: { c: CandidateState }) {
  const ph = phases(c);
  return (
    <div className="flex items-center gap-1">
      {ph.map((p, i) => (
        <div key={p.label} className="flex items-center gap-1">
          {i > 0 && <span className={cn("h-px w-3", p.state === "todo" ? "bg-zinc-800" : "bg-emerald-800")} />}
          <span
            className={cn(
              "flex items-center gap-1 text-[10px]",
              p.state === "done" && "text-emerald-500",
              p.state === "active" && "text-sky-300",
              p.state === "todo" && "text-zinc-600",
            )}
          >
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                p.state === "done" && "bg-emerald-500",
                p.state === "active" && "animate-pulse bg-sky-400",
                p.state === "todo" && "bg-zinc-700",
              )}
            />
            {p.label}
          </span>
        </div>
      ))}
    </div>
  );
}

function ScoreBar({
  label,
  passed,
  total,
  tone,
}: {
  label: string;
  passed?: number;
  total?: number;
  tone: string;
}) {
  const known = Boolean(total);
  const pct = known ? Math.round((100 * (passed ?? 0)) / (total as number)) : 0;
  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className="w-16 shrink-0 text-zinc-500">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
        <div className={cn("h-full rounded-full transition-all duration-700", tone)} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-9 shrink-0 text-right font-mono text-zinc-400">
        {known ? `${passed ?? 0}/${total}` : "—"}
      </span>
    </div>
  );
}

export function CandidateCard({ c, winner }: { c: CandidateState; winner: boolean }) {
  const logRef = useRef<HTMLDivElement>(null);
  const [showCode, setShowCode] = useState(false);
  useEffect(() => {
    // Scroll only the log box; scrollIntoView would hijack the page scroll on every event.
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [c.log.length]);

  const running = c.status === "running";
  const redteam = c.role === "redteam";

  return (
    <Card className={cn("overflow-hidden", winner && "ring-1 ring-emerald-500/70")}>
      {/* Header: identity + verdict */}
      <div className="flex items-center justify-between gap-2 border-b border-zinc-800 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-zinc-200">{c.label}</span>
          {redteam && (
            <span className="rounded border border-amber-900 bg-amber-950/50 px-1.5 py-0.5 text-[10px] text-amber-400">
              red-team
            </span>
          )}
          {winner && <span title="winner">🏆</span>}
        </div>
        <div className="flex items-center gap-2">
          <PhaseTracker c={c} />
          <Badge className={verdictClasses(c.status)}>{c.status}</Badge>
        </div>
      </div>

      <div className="space-y-2 p-3">
        {/* The sandbox itself: a machine window with its isolation boundary visible. */}
        <div
          className={cn(
            "rounded-lg border bg-black/40",
            running ? "border-sky-900/70" : "border-zinc-800",
          )}
        >
          <div className="flex items-center justify-between gap-2 rounded-t-lg border-b border-zinc-800/80 bg-zinc-900/80 px-2.5 py-1.5">
            <div className="flex min-w-0 items-center gap-1.5 font-mono text-[10px] text-zinc-500">
              <span className={cn("h-2 w-2 shrink-0 rounded-full", running ? "animate-pulse bg-sky-400" : "bg-zinc-600")} />
              <span className="truncate">
                sandbox·c{c.index}
                {c.worldHash ? (
                  <span className="text-violet-400"> · world {c.worldHash.slice(0, 8)}</span>
                ) : (
                  " · provisioning"
                )}
              </span>
            </div>
            <div className="flex shrink-0 items-center gap-1.5 text-[10px]">
              <span
                className={cn(
                  "rounded border px-1.5 py-0.5",
                  c.egressDenied > 0
                    ? "border-rose-900 bg-rose-950/50 text-rose-400"
                    : "border-zinc-800 bg-zinc-950 text-zinc-500",
                )}
                title="deny-all egress; only allowlisted hosts pass"
              >
                net {c.egressDenied > 0 ? `⛔×${c.egressDenied}` : "sealed"}
              </span>
              <span className="rounded border border-zinc-800 bg-zinc-950 px-1.5 py-0.5 text-zinc-500" title="no credentials inside the sandbox">
                0 secrets
              </span>
            </div>
          </div>
          <div ref={logRef} className="h-36 overflow-y-auto p-2 font-mono text-[11px] leading-relaxed">
            {c.log.length === 0 ? (
              <span className="text-zinc-600">provisioning…</span>
            ) : (
              <div className="space-y-1">
                {c.log.map((e, i) => (
                  <LogLine key={i} event={e} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Scores as bars: the in-sandbox vs held-out gap is visible at a glance. */}
        <div className="space-y-1">
          <ScoreBar label="in-sandbox" passed={c.inSandbox} total={c.sampleTotal} tone="bg-slate-500" />
          <ScoreBar
            label="held-out"
            passed={c.heldOut}
            total={c.heldTotal}
            tone={c.disqualified ? "bg-rose-700" : "bg-emerald-500"}
          />
        </div>

        {c.reason && <div className="text-[11px] text-zinc-500">{c.reason}</div>}
        {c.solution && (
          <div>
            <button
              onClick={() => setShowCode((v) => !v)}
              className="text-[11px] font-medium text-zinc-400 hover:text-zinc-200"
            >
              {showCode ? "hide solution.py ▴" : "view solution.py ▾"}
            </button>
            {showCode && (
              <pre className="mt-1 max-h-40 overflow-auto rounded-md border border-zinc-800 bg-black/50 p-2 font-mono text-[11px] leading-relaxed text-zinc-300">
                {c.solution.trimEnd()}
              </pre>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
