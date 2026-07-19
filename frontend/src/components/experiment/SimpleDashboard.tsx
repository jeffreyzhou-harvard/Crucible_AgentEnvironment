import { useState } from "react";
import type { CandidateState, ExperimentState } from "../../types";
import {
  attemptName,
  looksLikeFaking,
  plainStatus,
  plainStory,
  plainSummary,
  practiceScore,
  realScore,
  roleNote,
  type PlainScore,
  type Tone,
} from "../../lib/plain";
import { Card, CardContent } from "../ui/card";
import { cn } from "../../lib/utils";

const TONE: Record<Tone, { pill: string; bar: string; text: string; dot: string }> = {
  good: { pill: "border-emerald-700 bg-emerald-950/50 text-emerald-200", bar: "bg-emerald-500", text: "text-emerald-300", dot: "bg-emerald-400" },
  warn: { pill: "border-amber-700 bg-amber-950/50 text-amber-200", bar: "bg-amber-500", text: "text-amber-300", dot: "bg-amber-400" },
  bad: { pill: "border-rose-800 bg-rose-950/50 text-rose-200", bar: "bg-rose-600", text: "text-rose-300", dot: "bg-rose-500" },
  info: { pill: "border-sky-800 bg-sky-950/50 text-sky-200", bar: "bg-sky-500", text: "text-sky-300", dot: "bg-sky-400" },
  muted: { pill: "border-zinc-700 bg-zinc-900 text-zinc-300", bar: "bg-zinc-600", text: "text-zinc-400", dot: "bg-zinc-500" },
};

function StatChip({ n, label, tone }: { n: number; label: string; tone: Tone }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2">
      <span className={cn("text-2xl font-semibold tabular-nums", TONE[tone].text)}>{n}</span>
      <span className="text-xs leading-tight text-zinc-400">{label}</span>
    </div>
  );
}

function ScoreBar({ title, caption, score, tone }: { title: string; caption: string; score: PlainScore; tone: Tone }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-xs font-medium text-zinc-300">{title}</span>
        <span className={cn("text-xs font-semibold tabular-nums", score.known ? TONE[tone].text : "text-zinc-600")}>
          {score.known ? `${score.pct}%` : "—"}
          {score.known && <span className="ml-1 font-normal text-zinc-500">({score.passed}/{score.total})</span>}
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-zinc-800">
        <div className={cn("h-full rounded-full transition-all", TONE[tone].bar)} style={{ width: `${score.known ? score.pct : 0}%` }} />
      </div>
      <p className="mt-1 text-[11px] leading-tight text-zinc-500">{caption}</p>
    </div>
  );
}

function AttemptCard({ c, isWinner }: { c: CandidateState; isWinner: boolean }) {
  const [open, setOpen] = useState(false);
  const st = plainStatus(c);
  const practice = practiceScore(c);
  const real = realScore(c);
  const note = roleNote(c.role);
  const story = plainStory(c.log);

  return (
    <Card className={cn(isWinner && "ring-2 ring-emerald-500/60")}>
      <CardContent className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-zinc-100">{attemptName(c.index)}</span>
              {isWinner && <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-medium text-emerald-300">🏆 Winner</span>}
            </div>
            {note && <p className="mt-0.5 text-[11px] text-amber-400/80">{note}</p>}
          </div>
          <span className={cn("inline-flex shrink-0 items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium", TONE[st.tone].pill)}>
            <span>{st.emoji}</span>
            {st.label}
          </span>
        </div>

        <p className="text-xs leading-relaxed text-zinc-400">{st.blurb}</p>

        <div className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
          <ScoreBar
            title="Real hidden test"
            caption="The AI never saw these questions. This is the grade that counts."
            score={real}
            tone={st.tone === "good" ? "good" : real.known && real.pct < 50 ? "bad" : "warn"}
          />
          <ScoreBar
            title="Practice test"
            caption="The AI could see these — easy to ace by just memorizing the answers."
            score={practice}
            tone="muted"
          />
          {looksLikeFaking(c) && (
            <p className="rounded-md bg-amber-950/40 px-2 py-1.5 text-[11px] leading-snug text-amber-300">
              Notice the gap: great on practice, poor on the hidden test → it was faking, not solving.
            </p>
          )}
        </div>

        {c.egressDenied > 0 && (
          <p className="text-[11px] text-rose-400">
            🛡️ Tried to go online for answers {c.egressDenied} time{c.egressDenied > 1 ? "s" : ""} — blocked every time.
          </p>
        )}

        {story.length > 0 && (
          <div>
            <button onClick={() => setOpen((v) => !v)} className="text-[11px] font-medium text-zinc-400 hover:text-zinc-200">
              {open ? "Hide what it did ▴" : "Show what it did ▾"}
            </button>
            {open && (
              <ul className="mt-2 space-y-1.5 border-l border-zinc-800 pl-3">
                {story.map((line, i) => (
                  <li key={i} className={cn("flex gap-2 text-[11px] leading-snug", TONE[line.tone].text)}>
                    <span className="shrink-0">{line.icon}</span>
                    <span>{line.text}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function SimpleDashboard({
  exp,
  cands,
  live,
}: {
  exp: ExperimentState;
  cands: CandidateState[];
  live: boolean;
}) {
  const s = plainSummary(exp, cands);

  return (
    <div className="space-y-5">
      {/* The story, in one glance */}
      <Card>
        <CardContent className="space-y-4 p-5">
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">
              {live ? "Running now" : "Result"} · plain-English view
            </p>
            <h2 className="mt-1 text-xl font-semibold leading-snug text-zinc-50">
              {s.total} AI{s.total === 1 ? "" : "s"} tried to solve{" "}
              <span className="text-emerald-300">"{exp.taskTitle}"</span>.
            </h2>
            <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-zinc-400">
              Each AI took two tests: a <span className="text-zinc-200">practice test it could see</span>, and a{" "}
              <span className="text-zinc-200">hidden test it could not</span>. Only the hidden test counts — that's how we
              catch an AI that just memorized the practice answers instead of actually solving the problem.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <StatChip n={s.passed} label="solved it for real" tone="good" />
            <StatChip n={s.cheated} label="faked it (memorized)" tone="warn" />
            <StatChip n={s.stopped + s.working} label={s.working ? "still working / stopped" : "broke rules / failed"} tone="bad" />
            <StatChip n={s.onlineAttemptsBlocked} label="escape attempts blocked" tone="info" />
          </div>

          {s.finished && (
            <div
              className={cn(
                "rounded-lg border px-4 py-3 text-sm",
                s.winnerName
                  ? "border-emerald-800 bg-emerald-950/40 text-emerald-200"
                  : "border-zinc-800 bg-zinc-950/60 text-zinc-300",
              )}
            >
              {s.winnerName ? (
                <>
                  🏆 <span className="font-semibold">{s.winnerName}</span> wins — it's the best solution that actually
                  passed the hidden test. The ones that cheated or broke the rules were thrown out automatically.
                </>
              ) : (
                <>No winner: every attempt either faked it or broke the rules, so none could be trusted.</>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Safety, in plain terms */}
      <Card>
        <CardContent className="flex flex-wrap items-center gap-x-6 gap-y-2 p-4 text-xs text-zinc-400">
          <span className="font-medium text-zinc-300">Safety net</span>
          <span>🛡️ {s.onlineAttemptsBlocked} attempt{s.onlineAttemptsBlocked === 1 ? "" : "s"} to go online for answers — all blocked</span>
          <span>🔑 {s.secretsExposed} passwords or secrets exposed</span>
          {s.identicalStart && <span>⚖️ Every AI got the exact same starting point — a fair race</span>}
        </CardContent>
      </Card>

      {/* Per-attempt detail */}
      {cands.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {cands.map((c) => (
            <AttemptCard key={c.index} c={c} isWinner={c.index === exp.winner} />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="text-sm text-zinc-500">Getting the AIs ready…</CardContent>
        </Card>
      )}
    </div>
  );
}
