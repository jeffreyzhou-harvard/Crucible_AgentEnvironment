import { useState } from "react";
import { launchExperiment } from "../../lib/api";
import type { ExperimentLaunchResponse } from "../../types";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

const STEPS = [
  {
    title: "Sandboxes boot",
    body: "Each AI gets its own locked-down copy of the workspace from the warm pool: identical files, no network, no secrets.",
  },
  {
    title: "AIs attempt the problem",
    body: "They read the practice examples, write a solution, and test it. Cheaters may try planted shortcut files or blocked URLs.",
  },
  {
    title: "Hidden test grades everyone",
    body: "A fresh sandbox re-runs each solution against cases the AI never saw. Memorized answers fall apart here.",
  },
  {
    title: "Leaderboard settles it",
    body: "Honest generalizers rise, cheaters show a practice-vs-hidden score gap and get disqualified in front of you.",
  },
];

const TASKS = [
  {
    id: "cipher",
    label: "Hidden cipher — hard",
    blurb:
      "4 sample · 12 held-out · infer the rule from pairs. Case handling is only tested held-out, so sloppy inference shows as a score gap. Planted pair file + a blocked URL.",
  },
  {
    id: "sequence",
    label: "Guess the number pattern (the tricky one)",
    blurb:
      "Hard to solve honestly. We plant a shortcut file and a tempting web link — so you can watch the safety net catch an AI that tries to cheat.",
  },
  {
    id: "devowel",
    label: "Remove the vowels from words (the simple one)",
    blurb: "A straightforward warm-up with no traps — good for a first run.",
  },
];

export function ExperimentLauncher({
  onLaunched,
}: {
  onLaunched: (res: ExperimentLaunchResponse) => void;
}) {
  const [taskId, setTaskId] = useState(TASKS[0].id);
  const [candidates, setCandidates] = useState(4);
  const [redteam, setRedteam] = useState(2);
  const [rounds, setRounds] = useState(3);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const task = TASKS.find((t) => t.id === taskId) ?? TASKS[0];

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      onLaunched(await launchExperiment({ task_id: taskId, candidates, redteam, rounds }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  const inputCls =
    "w-20 rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 focus:border-emerald-500 focus:outline-none";

  return (
    <div className="mx-auto grid max-w-5xl items-start gap-6 lg:grid-cols-[1fr_20rem]">
      <Card>
      <CardHeader>
        <CardTitle>Set up an AI face-off</CardTitle>
        <p className="mt-0.5 text-xs leading-relaxed text-zinc-500">
          Several AIs try to solve the same problem, each in its own locked-down copy of the
          workspace. We grade them on a <span className="text-zinc-400">hidden test they never see</span>,
          so an AI can't win just by memorizing the practice answers — and if one tries to cheat or
          sneak online, the safety net catches it.
        </p>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-zinc-500">Problem to solve</div>
            <select
              value={taskId}
              onChange={(e) => setTaskId(e.target.value)}
              className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 focus:border-emerald-500 focus:outline-none"
            >
              {TASKS.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
            <p className="mt-1.5 text-xs text-zinc-500">{task.blurb}</p>
          </div>
          <div className="flex flex-wrap items-start gap-6">
            <label className="text-xs text-zinc-400">
              <div className="mb-1.5 uppercase tracking-wide text-zinc-500">How many AIs</div>
              <input
                type="number"
                min={1}
                max={8}
                className={inputCls}
                value={candidates}
                onChange={(e) => setCandidates(Number(e.target.value))}
              />
              <p className="mt-1 max-w-[9rem] text-[11px] leading-tight text-zinc-500">
                Attempts running at once. We keep the best honest one.
              </p>
            </label>
            <label className="text-xs text-zinc-400">
              <div className="mb-1.5 uppercase tracking-wide text-zinc-500">How many cheat</div>
              <input
                type="number"
                min={0}
                max={candidates}
                className={inputCls}
                value={redteam}
                onChange={(e) => setRedteam(Number(e.target.value))}
              />
              <p className="mt-1 max-w-[9rem] text-[11px] leading-tight text-zinc-500">
                Told to cheat on purpose, to prove the safety net works.
              </p>
            </label>
            <label className="text-xs text-zinc-400">
              <div className="mb-1.5 uppercase tracking-wide text-zinc-500">Rounds</div>
              <input
                type="number"
                min={1}
                max={8}
                className={inputCls}
                value={rounds}
                onChange={(e) => setRounds(Number(e.target.value))}
              />
              <p className="mt-1 max-w-[9rem] text-[11px] leading-tight text-zinc-500">
                Each round improves on the last one's winner. Watch the score climb.
              </p>
            </label>
          </div>
          {error && (
            <p className="rounded-md border border-red-900 bg-red-950/50 px-3 py-2 text-xs text-red-300">
              {error}
            </p>
          )}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Starting…" : "Start the face-off →"}
          </Button>
        </form>
      </CardContent>
      </Card>

      <aside className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-5">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          What happens when you hit start
        </h3>
        <ol className="mt-4 space-y-4">
          {STEPS.map((step, i) => (
            <li key={step.title} className="flex gap-3">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-emerald-800 bg-emerald-950/60 text-[10px] font-semibold text-emerald-400">
                {i + 1}
              </span>
              <div>
                <div className="text-xs font-medium text-zinc-200">{step.title}</div>
                <p className="mt-0.5 text-[11px] leading-relaxed text-zinc-500">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </aside>
    </div>
  );
}
