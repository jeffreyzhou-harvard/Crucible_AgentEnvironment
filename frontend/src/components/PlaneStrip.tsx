import type { TraceEvent } from "../types";
import { cn } from "../lib/utils";

interface PlaneDef {
  kind: string;
  label: string;
  sub: string;
  optimizes: string;
  active: string; // classes when this plane has fired
  detail: (payload: Record<string, unknown>) => string;
}

const PLANES: PlaneDef[] = [
  {
    kind: "plane.control",
    label: "Control",
    sub: "warm pool · scheduler",
    optimizes: "speed",
    active: "border-sky-500/60 bg-sky-500/10",
    detail: (p) => `sandbox ${String(p.sandbox_id ?? "").slice(0, 14)}`,
  },
  {
    kind: "plane.data",
    label: "Data",
    sub: "copy-on-write branch",
    optimizes: "reproducibility",
    active: "border-violet-500/60 bg-violet-500/10",
    detail: (p) => `${(p.branch_ids as unknown[] | undefined)?.length ?? 0} branch(es)`,
  },
  {
    kind: "plane.security",
    label: "Security",
    sub: "cred proxy · egress",
    optimizes: "isolation",
    active: "border-amber-500/60 bg-amber-500/10",
    detail: (p) => `${(p.egress as unknown[] | undefined)?.length ?? 0} egress hosts`,
  },
  {
    kind: "plane.execution",
    label: "Execution",
    sub: "docker · repos · agent",
    optimizes: "fidelity",
    active: "border-emerald-500/60 bg-emerald-500/10",
    detail: (p) => `${(p.repos as unknown[] | undefined)?.length ?? 0} repo(s)`,
  },
];

export function PlaneStrip({ events }: { events: TraceEvent[] }) {
  const byKind = new Map<string, Record<string, unknown>>();
  for (const e of events) byKind.set(e.kind, e.payload);

  return (
    <div className="space-y-2">
      <h3 className="px-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">
        Planes
      </h3>
      {PLANES.map((plane) => {
        const payload = byKind.get(plane.kind);
        const fired = payload !== undefined;
        return (
          <div
            key={plane.kind}
            className={cn(
              "rounded-lg border p-3 transition-colors",
              fired ? plane.active : "border-zinc-800 bg-zinc-900/40",
            )}
          >
            <div className="flex items-center justify-between">
              <span className={cn("text-sm font-medium", fired ? "text-zinc-100" : "text-zinc-400")}>
                {plane.label}
              </span>
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  fired ? "bg-emerald-400" : "bg-zinc-700",
                )}
              />
            </div>
            <div className="mt-0.5 text-[11px] text-zinc-500">{plane.sub}</div>
            <div className="mt-2 font-mono text-[11px] text-zinc-400">
              {fired ? plane.detail(payload) : `optimizes ${plane.optimizes}`}
            </div>
          </div>
        );
      })}
    </div>
  );
}
