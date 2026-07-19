import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { TraceEvent } from "../../types";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { ChartBox } from "./ChartBox";

interface Point {
  t: number; // seconds since experiment start
  cand: number;
  kind: string;
  detail: string;
}

const SERIES: Array<{ key: string; label: string; color: string; match: (e: TraceEvent) => boolean }> = [
  { key: "cmd", label: "command", color: "#34d399", match: (e) => e.kind === "tool_call" },
  { key: "msg", label: "agent message", color: "#38bdf8", match: (e) => e.kind === "agent.message" },
  {
    key: "egress-ok",
    label: "egress allowed",
    color: "#a78bfa",
    match: (e) => e.kind === "security.egress" && e.payload.allowed !== false,
  },
  {
    key: "egress-block",
    label: "egress blocked",
    color: "#fb7185",
    match: (e) => e.kind === "security.egress" && e.payload.allowed === false,
  },
  { key: "score", label: "scored", color: "#fbbf24", match: (e) => e.kind === "score" || e.kind === "verdict" },
];

function detail(e: TraceEvent): string {
  const p = e.payload;
  if (e.kind === "tool_call") return String(p.command ?? "");
  if (e.kind === "agent.message") return String(p.text ?? "");
  if (e.kind === "security.egress") return `${p.allowed === false ? "BLOCK" : "allow"} ${p.host ?? ""}`;
  if (e.kind === "score") return `in-sandbox ${p.in_sandbox}/${p.sample_total} · held-out ${p.held_out}/${p.held_total}`;
  if (e.kind === "verdict") return String(p.status ?? "");
  return e.kind;
}

interface TipProps {
  active?: boolean;
  payload?: Array<{ payload: Point }>;
}

function Tip({ active, payload }: TipProps) {
  if (!active || !payload?.length) return null;
  const pt = payload[0].payload;
  return (
    <div className="max-w-xs rounded-lg border border-zinc-700 bg-zinc-950 p-2 text-xs shadow-lg">
      <div className="font-medium text-zinc-200">
        candidate-{pt.cand} · t+{pt.t.toFixed(1)}s
      </div>
      <div className="truncate text-zinc-400">{pt.detail}</div>
    </div>
  );
}

/** What every agent was doing, second by second, on one shared clock. */
export function ActivityTimeline({ events, candidateCount }: { events: TraceEvent[]; candidateCount: number }) {
  const stamped = events.filter((e) => e.payload.candidate !== undefined);
  if (stamped.length < 2 || candidateCount === 0) return null;

  const t0 = Math.min(...stamped.map((e) => Date.parse(e.ts)));
  const byseries = SERIES.map((s) => ({
    ...s,
    points: stamped
      .filter(s.match)
      .map<Point>((e) => ({
        t: (Date.parse(e.ts) - t0) / 1000,
        cand: e.payload.candidate as number,
        kind: s.label,
        detail: detail(e),
      })),
  })).filter((s) => s.points.length > 0);

  if (byseries.length === 0) return null;

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Activity timeline — every agent on one clock</CardTitle>
        <span className="text-[11px] text-zinc-500">hover a dot for the exact command or event</span>
      </CardHeader>
      <CardContent>
        <ChartBox height={Math.max(160, candidateCount * 48 + 60)}>
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                type="number"
                dataKey="t"
                name="time"
                stroke="#71717a"
                fontSize={11}
                tickLine={false}
                unit="s"
                domain={[0, "dataMax"]}
              />
              <YAxis
                type="number"
                dataKey="cand"
                stroke="#71717a"
                fontSize={11}
                tickLine={false}
                width={38}
                domain={[-0.5, candidateCount - 0.5]}
                ticks={Array.from({ length: candidateCount }, (_, i) => i)}
                tickFormatter={(v) => `c${v}`}
                reversed
              />
              <ZAxis range={[36, 36]} />
              <Tooltip content={<Tip />} cursor={{ strokeDasharray: "3 3", stroke: "#ffffff22" }} />
              {byseries.map((s) => (
                <Scatter key={s.key} name={s.label} data={s.points} fill={s.color} isAnimationActive={false} />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </ChartBox>
        <div className="mt-2 flex flex-wrap gap-4 text-[11px] text-zinc-500">
          {byseries.map((s) => (
            <span key={s.key}>
              <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
