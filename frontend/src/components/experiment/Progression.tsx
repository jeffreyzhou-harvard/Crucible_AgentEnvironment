import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RoundPoint } from "../../types";
import { improvementSentence, roundPct } from "../../lib/plain";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

interface TipProps {
  active?: boolean;
  payload?: Array<{ payload: { round: number; pct: number; best: number; total: number } }>;
}

function Tip({ active, payload }: TipProps) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-950 p-2 text-xs shadow-lg">
      <div className="font-medium text-zinc-200">Round {r.round}</div>
      <div className="text-emerald-400">
        Hidden test: {r.pct}% ({r.best}/{r.total})
      </div>
    </div>
  );
}

export function Progression({ progression }: { progression: RoundPoint[] }) {
  if (progression.length < 2) return null;
  const rows = progression.map((p) => ({
    round: p.round + 1,
    pct: roundPct(p),
    best: p.bestHeldOut,
    total: p.heldTotal,
  }));
  const sentence = improvementSentence(progression);

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Getting better each round</CardTitle>
        <span className="text-[11px] text-zinc-500">score on the hidden test →</span>
      </CardHeader>
      <CardContent>
        {sentence && <p className="mb-3 text-sm leading-relaxed text-zinc-300">{sentence}</p>}
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: -12 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
            <XAxis
              dataKey="round"
              stroke="#71717a"
              fontSize={12}
              tickLine={false}
              tickFormatter={(v) => `Round ${v}`}
            />
            <YAxis domain={[0, 100]} stroke="#71717a" fontSize={12} width={40} tickLine={false} unit="%" />
            <Tooltip content={<Tip />} cursor={{ stroke: "#ffffff22" }} />
            <Line
              type="monotone"
              dataKey="pct"
              stroke="#10b981"
              strokeWidth={2.5}
              dot={{ r: 4, fill: "#10b981" }}
              activeDot={{ r: 6 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
