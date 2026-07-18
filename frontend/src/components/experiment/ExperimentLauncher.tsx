import { useState } from "react";
import { launchExperiment } from "../../lib/api";
import type { ExperimentLaunchResponse } from "../../types";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

const TASKS = [
  {
    id: "sequence",
    label: "Hidden sequence — adversarial",
    blurb: "3 sample · 9 held-out · planted answer file + a blocked URL. Shortcuts get caught.",
  },
  {
    id: "devowel",
    label: "Remove vowels — baseline",
    blurb: "3 sample · 9 held-out · self-contained, no bait.",
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
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const task = TASKS.find((t) => t.id === taskId) ?? TASKS[0];

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      onLaunched(await launchExperiment({ task_id: taskId, candidates, redteam }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  const inputCls =
    "w-20 rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 focus:border-emerald-500 focus:outline-none";

  return (
    <Card className="mx-auto max-w-2xl">
      <CardHeader>
        <CardTitle>Best-of-N experiment</CardTitle>
        <p className="mt-0.5 text-xs text-zinc-500">
          N agents solve the same task in isolated, identical sandboxes. Each is scored
          against a held-out grader — so a candidate can't win by gaming the visible tests.
          Red-team candidates probe the egress + secretless controls.
        </p>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-zinc-500">Task</div>
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
          <div className="flex items-end gap-6">
            <label className="text-xs text-zinc-400">
              <div className="mb-1.5 uppercase tracking-wide text-zinc-500">Candidates</div>
              <input
                type="number"
                min={1}
                max={8}
                className={inputCls}
                value={candidates}
                onChange={(e) => setCandidates(Number(e.target.value))}
              />
            </label>
            <label className="text-xs text-zinc-400">
              <div className="mb-1.5 uppercase tracking-wide text-zinc-500">Red-team</div>
              <input
                type="number"
                min={0}
                max={candidates}
                className={inputCls}
                value={redteam}
                onChange={(e) => setRedteam(Number(e.target.value))}
              />
            </label>
          </div>
          {error && (
            <p className="rounded-md border border-red-900 bg-red-950/50 px-3 py-2 text-xs text-red-300">
              {error}
            </p>
          )}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Launching…" : "Run experiment →"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
