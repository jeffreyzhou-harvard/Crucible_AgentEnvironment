import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CandidateState } from "../../types";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

interface Row {
  name: string;
  label: string;
  sample: number; // in-sandbox %
  held: number; // held-out %
  status: string;
  disq: boolean;
  winner: boolean;
}

function pct(n: number | undefined, total: number | undefined): number {
  if (!total || n === undefined) return 0;
  return Math.round((100 * n) / total);
}

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
      <div className="text-slate-400">in-sandbox: {r.sample}%</div>
      <div className="text-emerald-400">held-out: {r.held}%</div>
      <div className="mt-1 text-zinc-500">
        {r.disq ? `disqualified · ${r.status}` : r.status}
        {r.winner ? " · 🏆 winner" : ""}
      </div>
    </div>
  );
}

export function Leaderboard({
  cands,
  winner,
}: {
  cands: CandidateState[];
  winner: number | null;
}) {
  const rows: Row[] = [...cands]
    .sort((a, b) => a.index - b.index)
    .map((c) => ({
      name: `c${c.index}`,
      label: c.label,
      sample: pct(c.inSandbox, c.sampleTotal),
      held: pct(c.heldOut, c.heldTotal),
      status: c.status,
      disq: c.disqualified,
      winner: c.index === winner,
    }));

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Leaderboard — held-out vs in-sandbox</CardTitle>
        <span className="text-[11px] text-zinc-500">a gap = the reward-hack</span>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={rows} barGap={2}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
            <XAxis dataKey="name" stroke="#71717a" fontSize={12} tickLine={false} />
            <YAxis domain={[0, 100]} stroke="#71717a" fontSize={12} width={30} tickLine={false} />
            <Tooltip content={<Tip />} cursor={{ fill: "#ffffff08" }} />
            <Bar dataKey="sample" name="in-sandbox" fill="#475569" radius={[3, 3, 0, 0]} />
            <Bar dataKey="held" name="held-out" radius={[3, 3, 0, 0]}>
              <LabelList dataKey="held" position="top" fontSize={10} fill="#a1a1aa" />
              {rows.map((r) => (
                <Cell key={r.name} fill={r.winner ? "#10b981" : r.disq ? "#9f1239" : "#34d399"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div className="mt-2 flex gap-4 text-[11px] text-zinc-500">
          <span><span className="inline-block h-2 w-2 rounded-sm" style={{ background: "#475569" }} /> in-sandbox</span>
          <span><span className="inline-block h-2 w-2 rounded-sm" style={{ background: "#34d399" }} /> held-out (verified)</span>
          <span><span className="inline-block h-2 w-2 rounded-sm" style={{ background: "#9f1239" }} /> disqualified</span>
        </div>
      </CardContent>
    </Card>
  );
}
