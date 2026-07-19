import { Link } from "react-router-dom";
import { Accordion } from "../components/ui/accordion";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import logoUrl from "../assets/CrucibleLogo.png";

const REPO = "https://github.com/jeffreyzhou-harvard/AutoResearchEnvironment";
const CONCEPT = "https://neosigma.ai/blog/agent-workspaces";

// Element 2 - logo / brand
function Wordmark() {
  return (
    <span className="inline-flex items-center gap-2 text-base font-semibold tracking-tight text-zinc-100">
      <img src={logoUrl} alt="Crucible" className="h-7 w-7 object-contain" />
      Crucible
    </span>
  );
}

function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-zinc-900/80 bg-zinc-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3.5">
        <Wordmark />
        <nav className="flex items-center gap-5 text-sm text-zinc-400">
          <a href={CONCEPT} target="_blank" rel="noreferrer" className="hidden hover:text-zinc-200 sm:block">
            Concept
          </a>
          <a href={REPO} target="_blank" rel="noreferrer" className="hidden hover:text-zinc-200 sm:block">
            GitHub
          </a>
          <Link to="/console">
            <Button className="px-3 py-1.5 text-xs">Launch console</Button>
          </Link>
        </nav>
      </div>
    </header>
  );
}

// Element 6 - visual: a self-contained mock of the console
function ConsolePreview() {
  const planes = ["Control", "Data", "Security", "Execution"];
  const bars = [
    { label: "c0", pct: 100, tone: "bg-emerald-500", tag: "verified" },
    { label: "c1", pct: 78, tone: "bg-emerald-400/80", tag: "" },
    { label: "c2", pct: 11, tone: "bg-rose-800", tag: "overfit" },
    { label: "c3", pct: 0, tone: "bg-rose-900", tag: "blocked" },
  ];
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-4 shadow-2xl shadow-black/40">
      <div className="mb-3 flex flex-wrap gap-1.5">
        {planes.map((p) => (
          <span key={p} className="flex items-center gap-1.5 rounded-md border border-zinc-800 bg-zinc-950 px-2 py-1 text-[11px] text-zinc-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            {p}
          </span>
        ))}
      </div>
      <div className="mb-3 rounded-lg border border-violet-900/60 bg-violet-950/30 px-3 py-1.5 text-[11px] text-violet-200">
        🧬 4 sandboxes · identical world <span className="font-mono text-violet-400">a1c3…</span> ✓
      </div>
      <div className="space-y-1.5">
        {bars.map((b) => (
          <div key={b.label} className="flex items-center gap-2">
            <span className="w-6 font-mono text-[11px] text-zinc-500">{b.label}</span>
            <div className="h-4 flex-1 overflow-hidden rounded bg-zinc-800/60">
              <div className={`h-full ${b.tone}`} style={{ width: `${Math.max(b.pct, 4)}%` }} />
            </div>
            {b.tag && <span className="w-14 text-right text-[10px] text-zinc-500">{b.tag}</span>}
          </div>
        ))}
      </div>
      <div className="mt-3 space-y-0.5 rounded-lg border border-zinc-800 bg-black/50 p-2.5 font-mono text-[11px]">
        <div className="text-emerald-400"><span className="text-emerald-600">$</span> pytest -q</div>
        <div className="text-zinc-500">held-out 9/9 ✓ verified</div>
        <div className="text-rose-400">⛔ egress BLOCK · pastebin.com · not on allowlist</div>
      </div>
    </div>
  );
}

function Hero() {
  return (
    <section className="mx-auto max-w-5xl px-6 pt-16 pb-14">
      <div className="grid items-center gap-10 lg:grid-cols-2">
        <div>
          {/* Element 5 - social proof (context) */}
          <Badge className="border-zinc-700 text-zinc-400">Auto Research Summit · Build Session</Badge>
          {/* Element 3 - SEO title + subtitle */}
          <h1 className="mt-4 text-balance text-5xl font-semibold leading-[1.08] tracking-tight text-zinc-50 sm:text-6xl">
            The environment self-improving agents run in.
          </h1>
          <p className="mt-4 max-w-md text-base leading-relaxed text-zinc-400">
            Isolated, reproducible sandboxes where agents propose, test, and validate their own
            work, and can't cheat their way up the leaderboard.
          </p>
          {/* Element 4 - primary CTA */}
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <Link to="/console">
              <Button className="px-5 py-2.5">Launch the console →</Button>
            </Link>
            <a href={CONCEPT} target="_blank" rel="noreferrer">
              <Button variant="outline" className="px-5 py-2.5">Read the concept</Button>
            </a>
          </div>
          <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-xs text-zinc-500">
            <span>◆ 4 planes, one system</span>
            <span>◆ held-out verified scoring</span>
            <span>◆ 0 secrets in the sandbox</span>
          </div>
        </div>
        <ConsolePreview />
      </div>
    </section>
  );
}

// Problem → solution: state what breaks, then how Crucible fixes it.
function ProblemSolution() {
  const pairs = [
    {
      problem:
        "A self-improving agent has to run its own code to know whether the work is right. But that code is untrusted and model-generated: it can leak secrets, phone home, or wreck the host.",
      solution:
        "Every run is sealed off. Deny-all egress through an allowlist proxy, secretless credentials that never enter the box, and throwaway containers. The agent gets a real machine with nothing to exfiltrate.",
    },
    {
      problem:
        "Agents game evaluations. A candidate overfits the visible tests, posts a top score, and looks like a winner even though the solution never generalizes.",
      solution:
        "Every candidate is graded on held-out cases in a fresh sandbox it never touched. Gaming shows up as a gap between the in-sandbox and held-out scores, and a candidate that games the visible tests is disqualified, not rewarded.",
    },
    {
      problem:
        "Realistic environments are slow to start and drift between runs, so two attempts aren't comparable and results can't be reproduced.",
      solution:
        "Warm pools hand back a ready sandbox instantly, and copy-on-write branching starts every run from a byte-identical world. Fast, and fair to compare.",
    },
  ];
  return (
    <section className="mx-auto max-w-5xl px-6 py-14">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
        The problem, and how Crucible solves it
      </h2>
      <p className="mt-3 max-w-2xl text-base leading-relaxed text-zinc-400">
        To improve itself, an agent must run its own code to verify the work. That forces two hard
        problems at once: running untrusted code safely, and trusting the score it produces.
        Crucible is built to solve both.
      </p>
      <div className="mt-6 space-y-3">
        {pairs.map((p, i) => (
          <div key={i} className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
              <div className="text-xs font-medium uppercase tracking-wide text-rose-400/80">
                The problem
              </div>
              <p className="mt-1.5 text-sm leading-relaxed text-zinc-400">{p.problem}</p>
            </div>
            <div className="rounded-xl border border-emerald-900/50 bg-emerald-950/20 p-4">
              <div className="text-xs font-medium uppercase tracking-wide text-emerald-400/90">
                Crucible
              </div>
              <p className="mt-1.5 text-sm leading-relaxed text-zinc-300">{p.solution}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

// Element 7 - core benefits (the four planes)
function Benefits() {
  const items = [
    { icon: "⚡", title: "Speed", body: "Warm pools hand back a ready sandbox instantly. Spin up thousands, not one." },
    { icon: "🖥️", title: "Fidelity", body: "A real dev workstation with Docker, repos, and services, so what works here works in prod." },
    { icon: "🛡️", title: "Isolation", body: "Deny-all egress, an allowlist proxy, and secretless creds. Nothing to exfiltrate." },
    { icon: "🧬", title: "Reproducibility", body: "Copy-on-write branching gives every run a byte-identical world, so scores stay fair and comparable." },
  ];
  return (
    <section className="mx-auto max-w-5xl px-6 py-14">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Four planes, pushed at once</h2>
      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((it) => (
          <Card key={it.title}>
            <CardContent className="space-y-2">
              <div className="text-xl">{it.icon}</div>
              <div className="text-sm font-semibold text-zinc-100">{it.title}</div>
              <p className="text-xs leading-relaxed text-zinc-400">{it.body}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}

// Element 8 - testimonials (illustrative, role-based)
function Testimonials() {
  const quotes = [
    { initials: "RE", role: "Research engineer", text: "Best-of-N in isolated, identical sandboxes is exactly the eval substrate self-improvement loops keep reinventing." },
    { initials: "PL", role: "Platform lead", text: "The held-out grader means a candidate literally can't win by gaming the visible tests. That's the part everyone gets wrong." },
  ];
  return (
    <section className="mx-auto max-w-5xl px-6 py-14">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Why builders care</h2>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        {quotes.map((q) => (
          <Card key={q.role}>
            <CardContent className="space-y-3">
              <p className="text-sm leading-relaxed text-zinc-300">"{q.text}"</p>
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-800 text-[11px] font-medium text-zinc-300">
                  {q.initials}
                </span>
                <span className="text-xs text-zinc-500">{q.role}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}

// Element 9 - FAQ
function Faq() {
  return (
    <section className="mx-auto max-w-3xl px-6 py-14">
      <h2 className="mb-5 text-sm font-semibold uppercase tracking-wide text-zinc-500">FAQ</h2>
      <Accordion
        items={[
          { q: "What is Crucible?", a: "Sandbox environments where autonomous agents safely execute code, interact with real services, and verify their own work. It's the environment layer a self-improving research loop runs on." },
          { q: "Do I need Docker or an API key?", a: "No. The console ships a scripted mode that runs the whole flow with neither. Add Docker + an Anthropic key to run real agents in real containers." },
          { q: "What is a best-of-N experiment?", a: "N agents solve the same task in parallel, each in an isolated, byte-identical sandbox, scored against a held-out grader. Propose → test → validate → select: the atomic unit of self-improvement." },
          { q: "How do you stop an agent from gaming the score?", a: "Every candidate is scored on held-out cases it never sees, in a fresh sandbox. High in-sandbox but low held-out means overfitting, so the candidate is disqualified, not rewarded." },
          { q: "Is the agent's code contained?", a: "Yes. Deny-all egress with an allowlist proxy, secretless credentials, and network-disabled containers. Even a fully compromised sandbox has nothing to steal and nowhere to phone home." },
        ]}
      />
    </section>
  );
}

// Element 10 - final CTA
function FinalCta() {
  return (
    <section className="mx-auto max-w-5xl px-6 py-14">
      <Card className="border-emerald-900/50 bg-gradient-to-br from-emerald-950/30 to-zinc-900/40">
        <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
          <h2 className="text-2xl font-semibold tracking-tight text-zinc-50">
            Watch a self-improving loop run itself.
          </h2>
          <p className="max-w-md text-sm text-zinc-400">
            Launch a best-of-N experiment and see the planes light up, the agents race, and the
            leaderboard sort itself, live.
          </p>
          <Link to="/console">
            <Button className="px-6 py-2.5">Launch the console →</Button>
          </Link>
        </CardContent>
      </Card>
    </section>
  );
}

// Element 11 - footer (contact / legal)
function Footer() {
  return (
    <footer className="border-t border-zinc-900">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="flex flex-col justify-between gap-6 sm:flex-row">
          <div>
            <Wordmark />
            <p className="mt-2 max-w-xs text-xs text-zinc-500">
              The environment layer for autonomous research. Built for the Auto Research Summit &amp;
              Build Session.
            </p>
          </div>
          <div className="flex gap-12 text-sm">
            <div className="space-y-2">
              <div className="text-xs font-medium uppercase tracking-wide text-zinc-600">Product</div>
              <Link to="/console" className="block text-zinc-400 hover:text-zinc-200">Console</Link>
              <a href={REPO} target="_blank" rel="noreferrer" className="block text-zinc-400 hover:text-zinc-200">GitHub</a>
            </div>
            <div className="space-y-2">
              <div className="text-xs font-medium uppercase tracking-wide text-zinc-600">Learn</div>
              <a href={CONCEPT} target="_blank" rel="noreferrer" className="block text-zinc-400 hover:text-zinc-200">Concept</a>
            </div>
          </div>
        </div>
        <form
          onSubmit={(e) => e.preventDefault()}
          className="mt-8 flex max-w-sm gap-2"
          aria-label="Newsletter signup"
        >
          <input
            type="email"
            placeholder="you@lab.org"
            aria-label="Email address"
            className="flex-1 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-500 focus:outline-none"
          />
          {/* TODO: wire up newsletter capture */}
          <Button type="submit" variant="outline" className="px-3 py-2 text-xs">Keep me posted</Button>
        </form>
        <div className="mt-8 text-xs text-zinc-600">
          © 2026 Crucible · MIT (TODO) · <a href={CONCEPT} target="_blank" rel="noreferrer" className="hover:text-zinc-400">concept ↗</a>
        </div>
      </div>
    </footer>
  );
}

export default function Landing() {
  return (
    <div className="min-h-full">
      <Header />
      <main>
        <Hero />
        <ProblemSolution />
        <Benefits />
        <Testimonials />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
    </div>
  );
}
