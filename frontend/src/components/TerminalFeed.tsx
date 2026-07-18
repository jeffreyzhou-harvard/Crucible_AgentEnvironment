import { useEffect, useRef } from "react";
import type { TraceEvent } from "../types";

function str(v: unknown): string {
  return typeof v === "string" ? v : v == null ? "" : String(v);
}

function Line({ event }: { event: TraceEvent }) {
  const p = event.payload;
  switch (event.kind) {
    case "workspace.start":
      return (
        <div className="text-zinc-500">
          <span className="text-zinc-600">▶</span> workspace started
          {p.task_prompt ? <span className="text-zinc-400"> · {str(p.task_prompt)}</span> : null}
        </div>
      );
    case "plane.control":
    case "plane.data":
    case "plane.security":
    case "plane.execution":
      return (
        <div className="text-sky-300/70">
          <span className="text-sky-500/60">●</span> {event.kind.replace("plane.", "")} plane ready
        </div>
      );
    case "agent.start":
      return (
        <div className="text-zinc-400">
          <span className="text-emerald-500">▸</span> agent online{" "}
          <span className="text-zinc-600">({str(p.model)})</span>
        </div>
      );
    case "agent.message":
      return (
        <div className="whitespace-pre-wrap text-zinc-300">
          <span className="text-zinc-600">◆ </span>
          {str(p.text)}
        </div>
      );
    case "tool_call":
      return (
        <div className="font-mono text-emerald-400">
          <span className="text-emerald-600">$</span> {str(p.command)}
        </div>
      );
    case "command_output": {
      const failed = typeof p.exit_code === "number" && p.exit_code !== 0;
      return (
        <div
          className={
            "whitespace-pre-wrap border-l-2 pl-3 font-mono text-[12px] text-zinc-400 " +
            (failed ? "border-red-700" : "border-zinc-800")
          }
        >
          {str(p.output) || "(no output)"}
          {failed ? <span className="text-red-400"> [exit {String(p.exit_code)}]</span> : null}
        </div>
      );
    }
    case "agent.done": {
      const ok = p.succeeded === true;
      return (
        <div className={ok ? "text-emerald-400" : "text-amber-400"}>
          <span>■</span> agent finished — {ok ? "success" : "incomplete"}{" "}
          <span className="text-zinc-600">({str(p.stop_reason)})</span>
        </div>
      );
    }
    case "error":
      return (
        <div className="whitespace-pre-wrap text-red-400">
          <span>✕</span> {str(p.message)}
        </div>
      );
    case "workspace.end":
      return (
        <div className="text-zinc-600">▪ sandbox destroyed — trace persisted for replay</div>
      );
    default:
      return (
        <div className="text-zinc-600">
          {event.kind} {JSON.stringify(p)}
        </div>
      );
  }
}

export function TerminalFeed({ events }: { events: TraceEvent[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [events.length]);

  return (
    <div className="h-full overflow-y-auto rounded-xl border border-zinc-800 bg-black/40 p-4 font-mono text-[13px] leading-relaxed">
      {events.length === 0 ? (
        <div className="text-zinc-600">Waiting for the sandbox to come online…</div>
      ) : (
        <div className="space-y-1.5">
          {events.map((e, i) => (
            <Line key={i} event={e} />
          ))}
          <div ref={endRef} />
        </div>
      )}
    </div>
  );
}
