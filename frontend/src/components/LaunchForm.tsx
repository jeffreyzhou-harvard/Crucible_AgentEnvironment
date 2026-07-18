import { useState } from "react";
import { launchWorkspace } from "../lib/api";
import type { LaunchResponse } from "../types";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";

const DEFAULT_PROMPT =
  "Clone is already done. Explore the repository, run its test suite, and report " +
  "whether the tests pass. If any fail, propose a fix.";

export function LaunchForm({ onLaunched }: { onLaunched: (res: LaunchResponse) => void }) {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [repoUrl, setRepoUrl] = useState("https://github.com/psf/requests");
  const [repoRef, setRepoRef] = useState("main");
  const [egress, setEgress] = useState("github.com, pypi.org");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await launchWorkspace({
        agent_id: "demo-agent",
        task_prompt: prompt,
        repos: repoUrl.trim() ? [{ url: repoUrl.trim(), ref: repoRef.trim() || "main" }] : [],
        datasets: [],
        extra_egress_hosts: egress
          .split(",")
          .map((h) => h.trim())
          .filter(Boolean),
      });
      onLaunched(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  const labelCls = "block text-xs font-medium uppercase tracking-wide text-zinc-500 mb-1.5";
  const inputCls =
    "w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 " +
    "placeholder:text-zinc-600 focus:border-emerald-500 focus:outline-none";

  return (
    <Card className="mx-auto max-w-2xl">
      <CardHeader>
        <h2 className="text-sm font-semibold text-zinc-200">Launch a workspace</h2>
        <p className="mt-0.5 text-xs text-zinc-500">
          Spins up an isolated sandbox and turns a Claude agent loose in it.
        </p>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className={labelCls}>Task</label>
            <textarea
              className={`${inputCls} min-h-[96px] resize-y`}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className={labelCls}>Repository</label>
              <input
                className={inputCls}
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
              />
            </div>
            <div>
              <label className={labelCls}>Ref</label>
              <input
                className={inputCls}
                value={repoRef}
                onChange={(e) => setRepoRef(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className={labelCls}>Egress allowlist</label>
            <input
              className={inputCls}
              value={egress}
              onChange={(e) => setEgress(e.target.value)}
              placeholder="github.com, pypi.org"
            />
          </div>
          {error && (
            <p className="rounded-md border border-red-900 bg-red-950/50 px-3 py-2 text-xs text-red-300">
              {error}
            </p>
          )}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Launching…" : "Launch workspace →"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
