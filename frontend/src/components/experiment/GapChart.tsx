import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ReferenceLine,
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
  gap: number;
  sample: number;
  held: number;
  disq: boolean;
}

function pct(n: number | undefined, total: number | undefined): number {
  if (!total || n === undefined) return 0;
  return Math.round((100 * n) / total);
}

function gapColor(r: Row): string {
  if (r.disq) return "#9f1239";
  if (r.gap >= 25) return "#f59e0b";
  if (r.gap <= 0) return "#34d399";
  return "#64748b";
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
      <div className="text-zinc-400">in-sandbox {r.sample}% − held-out {r.held}%</div>
      <div className={r.gap >= 25 ? "text-amber-400" : "text-zinc-500"}>
        gap: {r.gap > 0 ? "+" : ""}{r.gap} pts{r.gap >= 25 ? " · overfit signature" : ""}
      </div>
    </div>
  );
}

/** The reward-hack detector, isolated: in-sandbox minus held-out, per candidate. */
export function GapChart({ cands }: { cands: CandidateState[] }) {
  const rows: Row[] = [...cands]
    .sort((a, b) => a.index - b.index)
    .filter((c) => c.sampleTotal && c.heldTotal)
    .map((c) => {
      const sample = pct(c.inSandbox, c.sampleTotal);
      const held = pct(c.heldOut, c.heldTotal);
      return {
        name: `c${c.index}`,
        label: c.label,
        gap: sample - held,
        sample,
        held,
        disq: c.disqualified,
      };
    });

  if (rows.length === 0) return null;

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Overfit gap — in-sandbox minus held-out</CardTitle>
        <span className="text-[11px] text-zinc-500">near 0 = honest · large = memorized</span>
      </CardHeader>
      <CardContent>
        <ChartBox height={Math.max(140, rows.length * 44 + 40)}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 36, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
              <XAxis type="number" domain={[-20, 100]} stroke="#71717a" fontSize={11} tickLine={false} unit=" pts" />
              <YAxis type="category" dataKey="name" stroke="#71717a" fontSize={12} width={34} tickLine={false} />
              <ReferenceLine x={0} stroke="#3f3f46" />
              <Tooltip content={<Tip />} cursor={{ fill: "#ffffff08" }} />
              <Bar dataKey="gap" radius={[0, 3, 3, 0]} isAnimationActive={false}>
                <LabelList
                  dataKey="gap"
                  position="right"
                  fontSize={10}
                  fill="#a1a1aa"
                  formatter={(v: number) => (v > 0 ? `+${v}` : `${v}`)}
                />
                {rows.map((r) => (
                  <Cell key={r.name} fill={gapColor(r)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartBox>
        <div className="mt-2 flex gap-4 text-[11px] text-zinc-500">
          <span><span className="inline-block h-2 w-2 rounded-sm" style={{ background: "#34d399" }} /> generalizes</span>
          <span><span className="inline-block h-2 w-2 rounded-sm" style={{ background: "#f59e0b" }} /> big gap (overfit)</span>
          <span><span className="inline-block h-2 w-2 rounded-sm" style={{ background: "#9f1239" }} /> disqualified</span>
        </div>
      </CardContent>
    </Card>
  );
}
