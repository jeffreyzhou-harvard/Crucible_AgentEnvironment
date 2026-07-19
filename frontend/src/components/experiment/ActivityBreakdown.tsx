import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CandidateState } from "../../types";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { ChartBox } from "./ChartBox";

interface Row {
  name: string;
  label: string;
  commands: number;
  messages: number;
  egressAllowed: number;
  egressBlocked: number;
}

const SERIES: Array<{ key: keyof Row; label: string; color: string }> = [
  { key: "commands", label: "commands run", color: "#34d399" },
  { key: "messages", label: "agent messages", color: "#38bdf8" },
  { key: "egressAllowed", label: "egress allowed", color: "#a78bfa" },
  { key: "egressBlocked", label: "egress blocked", color: "#fb7185" },
];

interface TipProps {
  active?: boolean;
  payload?: Array<{ payload: Row }>;
}

function Tip({ active, payload }: TipProps) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-950 p-2 text-xs shadow-lg">
      <div className="font-medium text-zinc-200">{r.label}</div>
      {SERIES.map((s) => (
        <div key={s.key} style={{ color: s.color }}>
          {s.label}: {r[s.key] as number}
        </div>
      ))}
    </div>
  );
}

/** How each agent spent its run: work vs talk vs network behavior. */
export function ActivityBreakdown({ cands }: { cands: CandidateState[] }) {
  const rows: Row[] = [...cands]
    .sort((a, b) => a.index - b.index)
    .map((c) => {
      let commands = 0;
      let messages = 0;
      let egressAllowed = 0;
      for (const e of c.log) {
        if (e.kind === "tool_call") commands += 1;
        else if (e.kind === "agent.message") messages += 1;
        else if (e.kind === "security.egress" && e.payload.allowed !== false) egressAllowed += 1;
      }
      return {
        name: `c${c.index}`,
        label: c.label,
        commands,
        messages,
        egressAllowed,
        egressBlocked: c.egressDenied,
      };
    })
    .filter((r) => r.commands + r.messages + r.egressAllowed + r.egressBlocked > 0);

  if (rows.length === 0) return null;

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Agent activity — what each one actually did</CardTitle>
        <span className="text-[11px] text-zinc-500">cheaters skew toward blocked egress</span>
      </CardHeader>
      <CardContent>
        <ChartBox height={200}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 4, right: 12, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
              <XAxis dataKey="name" stroke="#71717a" fontSize={12} tickLine={false} />
              <YAxis allowDecimals={false} stroke="#71717a" fontSize={11} tickLine={false} />
              <Tooltip content={<Tip />} cursor={{ fill: "#ffffff08" }} />
              <Legend wrapperStyle={{ fontSize: 11, color: "#71717a" }} iconSize={8} />
              {SERIES.map((s) => (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  stackId="a"
                  fill={s.color}
                  isAnimationActive={false}
                  radius={s.key === "egressBlocked" ? [3, 3, 0, 0] : undefined}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartBox>
      </CardContent>
    </Card>
  );
}
