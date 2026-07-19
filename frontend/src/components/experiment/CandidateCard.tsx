import { useEffect, useRef, useState } from "react";
import { verdictClasses } from "../../lib/experiment";
import type { CandidateState, TraceEvent } from "../../types";
import { Badge } from "../ui/badge";
import { Card, CardContent, CardHeader } from "../ui/card";
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

export function CandidateCard({ c, winner }: { c: CandidateState; winner: boolean }) {
  const logRef = useRef<HTMLDivElement>(null);
  const [showCode, setShowCode] = useState(false);
  useEffect(() => {
    // Scroll only the log box; scrollIntoView would hijack the page scroll on every event.
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [c.log.length]);

  const sample = c.sampleTotal ? `${c.inSandbox ?? 0}/${c.sampleTotal}` : "—";
  const held = c.heldTotal ? `${c.heldOut ?? 0}/${c.heldTotal}` : "—";

  return (
    <Card className={cn(winner && "ring-1 ring-emerald-500/70")}>
      <CardHeader className="flex items-center justify-between gap-2 py-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-zinc-200">{c.label}</span>
          {winner && <span title="winner">🏆</span>}
        </div>
        <Badge className={verdictClasses(c.status)}>{c.status}</Badge>
      </CardHeader>
      <CardContent className="space-y-2 p-3">
        <div className="flex items-center gap-3 text-xs">
          <span className="text-slate-400">in-sandbox {sample}</span>
          <span className="text-emerald-400">held-out {held}</span>
          {c.egressDenied > 0 && (
            <span className="text-rose-400">{c.egressDenied} egress blocked</span>
          )}
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
        <div ref={logRef} className="h-40 overflow-y-auto rounded-md border border-zinc-800 bg-black/40 p-2 font-mono text-[11px] leading-relaxed">
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
      </CardContent>
    </Card>
  );
}
