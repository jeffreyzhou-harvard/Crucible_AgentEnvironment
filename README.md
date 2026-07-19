<p align="center">
  <img src="CrucibleLogo.png" alt="Crucible" width="160" />
</p>

<h1 align="center">Crucible</h1>

<p align="center">
  Isolated, reproducible sandboxes where self-improving agents run untrusted code — and can't game the score.
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#best-of-n-experiments">Best-of-N experiments</a> ·
  <a href="#api">API</a> ·
  <a href="docs/architecture.md">Architecture</a>
</p>

---

## The problem

A self-improving agent must run its own code to know whether its work is right. That forces two hard problems at once:

1. **Running untrusted code safely.** Model-generated code can leak secrets, phone home, or damage the host. Giving an agent a real development environment usually means giving it your network, your credentials, and your machine.
2. **Trusting the score it produces.** Agents game evaluations. A candidate that overfits the visible tests posts a top score and looks like a winner, even though the solution never generalizes. If the leaderboard can be cheated, the self-improvement loop optimizes for cheating.

Existing approaches trade these off against each other — and against speed. Realistic environments are slow to start and drift between runs, so two attempts aren't comparable and results can't be reproduced.

## The solution

Crucible is the environment layer for autonomous research. Every agent run gets a real, disposable development workstation that is:

- **Sealed off.** Deny-all egress behind an allowlist proxy, secretless credentials injected at the proxy (secrets never enter the sandbox), and hardened throwaway containers. A fully compromised sandbox has nothing to steal and nowhere to phone home.
- **Reproducible.** Copy-on-write data branching starts every run from a byte-identical world, verified by a content-hash receipt before the agent may touch the data. Scores are fair to compare because the starting states are provably the same.
- **Honestly scored.** Every candidate is graded on held-out cases in a fresh sandbox it never touched. Gaming shows up as a gap between the in-sandbox and held-out scores — the gap *is* the reward hack, and the candidate is disqualified, not rewarded.
- **Fast.** Warm pools boot sandboxes ahead of demand, so acquiring one is a pointer swap instead of a cold start. Intent signals from the UI start warming a sandbox before the launch button is pressed.

## How it works

The architecture is split into four planes, each optimizing for one property, plus a cross-cutting trace layer. Planes meet only through narrow interfaces, so each can be implemented, tested, and replaced independently.

| Plane | Optimizes for | Package | Responsibilities |
|-------|---------------|---------|------------------|
| **Control** | Speed | `control/` | Warm pools, demand-predicting scheduler, intent-driven speculative provisioning |
| **Execution** | Fidelity | `execution/` | Full dev workstation: writable FS, cloned repos, Docker, agent loop |
| **Security & Network** | Isolation | `security/` | Secretless credential proxy, egress allowlist, audit log, hardened runtime |
| **Data** | Reproducibility | `data/` | Dataset provisioning, copy-on-write branching, content-hash health checks |

The **trace** layer (`trace/`) records every execution durably, outside the sandbox. A sandbox can be destroyed while its full trajectory remains available for replay, debugging, and evaluation.

```
request ─▶ [control]   schedule / claim warm sandbox
        ─▶ [data]      branch datasets from read-only snapshot
        ─▶ [security]  attach credential proxy + network policy
        ─▶ [execution] attach agent, run to completion
        ─▶ [trace]     persist full trajectory
        ─▶ [control]   recycle or destroy sandbox
```

Security attaches *before* execution by design: no agent-controlled code runs before isolation is live. See [docs/architecture.md](docs/architecture.md) for the full design.

## Quick start

### Prerequisites

- Python 3.11+
- Node 18+ (for the web console)
- Docker (optional — only needed to run real agents)

### Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
make dev          # API on :8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev       # console on :5173
```

Open http://localhost:5173. By default (`AWS_RUNTIME_BACKEND=mock`) the entire flow — launch, live trace stream, teardown — runs with **no Docker and no API key**, using a scripted execution plane.

### Run real agents

1. Start Docker (the runtime pulls `python:3.11` on first use).
2. `export ANTHROPIC_API_KEY=...`
3. In `.env`, set `AWS_RUNTIME_BACKEND=docker`.
4. Launch a workspace from the console: enter a task and a public repo, and watch the planes light up as the agent's commands stream into the terminal.

## Best-of-N experiments

The workspace is the substrate; the experiment is the loop that runs on it. A Best-of-N experiment launches N agents on the same task in parallel, each in its own isolated, byte-identical sandbox, then scores every candidate against a **held-out grader** the candidate never sees. This is the atomic unit of a self-improvement loop — *propose → test → validate → select* — with the environment's guarantees doing real safety work:

- **Reproducibility receipt** — every candidate prints a hash of its starting world; the console shows they're identical.
- **Two-number score** — *in-sandbox* vs. *held-out*. A candidate that overfits the visible tests scores high in-sandbox and low held-out, and is disqualified.
- **Egress controls** — network is deny-all; an allowlist-gated `web_fetch` broker denies off-list hosts, and every allow/block decision lands in a shared audit log.
- **Isolation** — untrusted, self-generated code (including the grader's run of it) executes only inside network-disabled containers, never on the host.

Experiments run on either backend with the same event stream and dashboard: `mock` for a fully scripted run, or `docker` + an API key for real Claude agents graded in fresh throwaway sandboxes.

## API

```
POST /v1/workspaces:launch            → {workspace_id, trace_id}
POST /v1/workspaces/{id}:destroy      → force-teardown a live workspace (idempotent)
POST /v1/experiments:launch           → {experiment_id, trace_id}
POST /v1/intent:signal                → speculatively warm a shaped sandbox
GET  /v1/pool                         → warm-pool stats (size, hit rate, what's hot)
GET  /v1/traces/{trace_id}            → replay a recorded trajectory
GET  /v1/security/egress-audit        → every allow/block decision
WS   /v1/traces/{trace_id}/stream     → live trace stream (replays history, then streams)
```

The API is streaming-first: launching returns ids immediately, the lifecycle runs in the background, and the WebSocket stream replays history before going live — a client sees the whole trajectory whether it connects before, during, or after the run.

## Configuration

Configuration is environment-driven (see `.env.example` for the full list). The most important switches:

| Variable | Values | Purpose |
|----------|--------|---------|
| `AWS_RUNTIME_BACKEND` | `mock` \| `docker` | Scripted demo vs. real containers |
| `AWS_SECURITY_BACKEND` | `mock` \| `proxy` | No-op vs. real secretless egress proxy |
| `AWS_DATA_BRANCH_BACKEND` | `copy` \| `cow` | Plain copy vs. copy-on-write clones (APFS clonefile / Linux reflink) |
| `AWS_TRACE_STORE_URI` | path | Enable durable JSONL trace storage + replay |
| `AWS_WARM_POOL_MIN_SIZE` / `MAX_SIZE` | int | Warm-pool bounds |
| `AWS_SANDBOX_HARDEN` | bool | Drop all capabilities, `no-new-privileges`, cgroup limits |

## Project layout

```
src/agent_workspaces/
├── config.py          # settings (pydantic-settings)
├── models.py          # shared domain models (Pydantic)
├── orchestrator.py    # streaming lifecycle: begin() + run_lifecycle()
├── main.py            # FastAPI app + composition root
├── api/routes.py      # launch/experiment endpoints + WS trace stream
├── control/           # Control plane   — scheduler, warm pool, intent
├── execution/         # Execution plane — sandbox, runtime, agent loop
├── security/          # Security plane  — credential proxy, network policy
├── data/              # Data plane      — provisioner, branching, health
├── experiment/        # Best-of-N: tasks · grader · runners
└── trace/             # bus (pub/sub) · tracer · recorder

frontend/              # React + Vite + TypeScript console
docs/                  # architecture notes
```

## Development

```bash
make test         # run the test suite
make lint         # ruff
make typecheck    # mypy
make fmt          # auto-format + fix imports
```

## Security model and limitations

- The Docker runtime is hardened (all capabilities dropped, `no-new-privileges`, memory/pids/cpu limits) but still shares the host kernel. For hostile-by-design workloads, use a gVisor/Kata or microVM (Firecracker) runtime backend — the runtime interface is pluggable for exactly this reason.
- The secretless credential proxy is single-tenant: one shared proxy whose allowlist and credential map are set per run. N parallel experiment candidates therefore use per-candidate isolation (deny-all + policy-gated `web_fetch`) rather than routing through the shared proxy.
- The `mock` security backend enforces nothing and exists only for local development.

## Acknowledgements

Crucible's design is inspired by [NeoSigma's *Agent Workspaces*](https://neosigma.ai/blog/agent-workspaces).

> "An agent is only as capable as the environment it can safely act in."

## License

License TBD. A `LICENSE` file will be added before the first tagged release.
