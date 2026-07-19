# Crucible

**Crucible** is a template for building sandbox environments where autonomous
AI agents can safely execute code, interact with real services, and verify their own
work. Inspired by [NeoSigma's *Agent Workspaces*](https://neosigma.ai/blog/agent-workspaces).

> "An agent is only as capable as the environment it can safely act in."

This repo started as a **scaffold** — structure, interfaces, and domain models with
the behavior marked `TODO:`. The planes are now implemented end-to-end (see *Status*
below): warm pools that really boot containers, copy-on-write data branches with
cryptographic identical-start receipts, a real secretless egress proxy, durable
traces, and a hardened Docker runtime. The remaining `TODO:`s point at the next
frontier (microVM backends, Neon/ZFS branching, multi-tenant quotas).

## The four planes

The architecture is organized into four planes that are pushed on simultaneously
rather than traded off against each other:

| Plane | Optimizes for | Package | Responsibilities |
|-------|---------------|---------|------------------|
| **Control** | Speed | `control/` | Warm pools, demand-predicting scheduler, intent prediction |
| **Execution** | Fidelity | `execution/` | Full dev workstation: writable FS, cloned repos, Docker, MCP servers |
| **Security & Network** | Isolation | `security/` | Secretless credential proxy, ingress/egress policy, kernel/HW isolation |
| **Data** | Reproducibility | `data/` | Dataset provisioning, copy-on-write DB branching, health checks |

A fifth cross-cutting concern, **trace** (`trace/`), records every execution so a
sandbox can be destroyed while its trajectory remains available for replay, debugging,
and evaluation.

## Status: all four planes are live

Every plane now has a real implementation behind its interface, selected in
`main.py:build_orchestrator` from settings:

- **Execution plane — real.** A Docker container per sandbox, a repo cloned into it,
  and a **Claude agent loop** (`bash` tool → commands executed in the container).
  Containers are hardened by default: every capability dropped, `no-new-privileges`,
  memory/pids/cpu limits (`AWS_SANDBOX_HARDEN`).
- **Control plane — real.** A runtime-backed **warm pool** that boots containers
  *ahead of demand* (refill loop starts with the app), an EWMA **demand predictor**
  that pre-scales it, shape-keyed claims so a warm sandbox is only reused when it
  matches the request, and an **intent predictor** (`POST /v1/intent:signal`) that
  starts warming a sandbox the moment the UI's launch form opens. Every run's trace
  carries the receipt: `warm_hit` + `acquire_ms` (warm claims are pointer swaps;
  cold starts pay the boot). Observability at `GET /v1/pool`.
- **Data plane — real.** `AWS_DATA_BRANCH_BACKEND=cow` branches the reference
  snapshot with **copy-on-write filesystem clones** (APFS `clonefile` / Linux
  reflink — O(metadata), not O(bytes)), and every branch carries a **content-hash
  receipt** the health checker verifies against the reference before the agent may
  touch the data: identical starting worlds, *proven*, per run. Missing snapshots
  fail loudly instead of silently starting empty.
- **Security plane — real** (`AWS_SECURITY_BACKEND=proxy`). A secretless egress
  proxy: allowlist enforcement, credential injection at egress (secrets never enter
  the sandbox), live `security.egress` events, shared audit log. The experiment's
  `web_fetch` broker performs **real policy-gated fetches** for allowlisted hosts.
- **Trace plane — durable.** Set `AWS_TRACE_STORE_URI` and every trace is appended
  to JSONL that survives a process restart; replay any run via
  `GET /v1/traces/{trace_id}`. Destroy the sandbox — keep the trajectory.
- **Frontend — real.** A React "mission control" (`frontend/`) that launches a
  workspace, lights up the four planes as they fire (now with warm-hit/cold-start
  timings and the world-hash receipt), and streams the agent's terminal.

Set `AWS_RUNTIME_BACKEND=mock` to run the entire lifecycle with **no Docker and no API
key** — the mock execution plane still emits a trace, so the frontend works end-to-end.

### Control-plane API surface

```
POST /v1/workspaces:launch            → {workspace_id, trace_id}
POST /v1/workspaces/{id}:destroy      → force-teardown a live workspace (idempotent)
POST /v1/experiments:launch           → {experiment_id, trace_id}
POST /v1/intent:signal                → speculatively warm a shaped sandbox
GET  /v1/pool                         → warm-pool stats (size, hit rate, what's hot)
GET  /v1/traces/{trace_id}            → replay a recorded trajectory
GET  /v1/security/egress-audit        → every allow/block decision
WS   /v1/traces/{trace_id}/stream     → live trace stream
```

## Best-of-N experiments — the autoresearch demo

The workspace is the substrate; the **experiment** is the loop that runs on it. The
`Best-of-N` tab launches N agents that solve the same task in parallel, each in its own
isolated, byte-identical sandbox, then scores every candidate against a **held-out
grader** the candidate never sees. This is the atomic unit of a self-improvement loop —
*propose → test → validate → select* — and it makes the environment's guarantees do real
safety work:

- **Reproducibility receipt** — every candidate prints a hash of its starting world;
  the UI shows they're identical (the copy-on-write "same world" claim, proven live).
- **Two-number score** — *in-sandbox* vs *held-out*. A candidate that games the visible
  tests scores high in-sandbox and low held-out; the gap **is** the reward-hack, and it's
  disqualified. You can't cheat your way up the leaderboard.
- **Egress + secretless controls** — network is deny-all; an allowlist-gated `web_fetch`
  broker denies off-list hosts (shown in red). Red-team candidates probe these controls
  and get caught.
- **Isolation** — untrusted, self-generated code (including the grader's run of it)
  executes only inside network-disabled containers, never on the host.

### One security model, two consumers

The experiment and the single-run **security plane** (`security_backend=proxy`) share one
egress model rather than reimplementing it:

- **One policy** — `security/policy.py:host_allowed`, against one allowlist (`egress_hosts`).
- **One event** — both stream `security.egress` (`{allowed, host, path, reason, credential_injected}`),
  so the frontend has a single renderer.
- **One audit** — experiment denials are recorded into the same `EgressAuditLog`, so
  `GET /v1/security/egress-audit` shows single-run *and* experiment attempts together.

The live proxy is single-tenant (one global allowlist), so N parallel candidates use
per-candidate isolation (deny-all + policy-gated `web_fetch`) rather than routing through
the shared proxy. TODO: a per-candidate proxy instance would give each candidate the full
credential-injecting proxy path.

Two backends, same event stream + dashboard:

- **Scripted** (default, `AWS_RUNTIME_BACKEND=mock`) — a believable run with no Docker
  and no API key. Reliable for a stage demo.
- **Real** (`AWS_RUNTIME_BACKEND=docker` + `ANTHROPIC_API_KEY`) — Claude agents in
  containers, scored by the external held-out grader in fresh throwaway sandboxes.

```
POST /v1/experiments:launch → {experiment_id, trace_id}
WS   /v1/traces/{trace_id}/stream   # one stream; events stamped per candidate
```

## Lifecycle

```
request ─▶ [control] schedule / claim warm sandbox
        ─▶ [data]     branch datasets from read-only snapshot
        ─▶ [security] attach credential proxy + network policy
        ─▶ [execution] attach agent, run to completion
        ─▶ [trace]    persist full trajectory
        ─▶ [control]  recycle or destroy sandbox
```

The `orchestrator.py` module wires these together; each plane is independently
swappable behind its interface.

## Project layout

```
src/agent_workspaces/
├── config.py          # settings (pydantic-settings)
├── models.py          # shared domain models (Pydantic)
├── orchestrator.py    # streaming lifecycle: begin() + run_lifecycle()
├── main.py            # FastAPI app + composition root (mock vs docker)
├── api/routes.py      # launch/experiments endpoints + WS /v1/traces/{id}/stream
├── control/           # Control plane  — scheduler, warm pool, intent
├── execution/         # Execution plane — sandbox, runtime (docker), agent (Claude)
├── security/          # Security plane  — credential proxy, network, isolation
├── data/              # Data plane      — provisioner, branching, health
├── experiment/        # Best-of-N: tasks · grader · scripted · docker_runner · runner
└── trace/             # bus (pub/sub) · tracer · recorder

frontend/              # React + Vite + TS + Tailwind + Recharts dashboard
```

> The dashboard follows the `frontend-components` skill's patterns (Card layout,
> loading/empty/error states, Recharts charts, custom tooltips, Badge color helpers,
> a `DashboardShell`-style container). It's adapted from that skill's Next.js 15 / SWR /
> React 19 stack to this repo's Vite + React 18 setup, and uses **WebSocket streaming**
> instead of SWR polling — the right call for a live race — and **Recharts 2.x** (React 18).

## Getting started

**Backend** (Python 3.11+):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # then edit
make dev                  # uvicorn on :8000 with reload
make test                 # runs the mock-lifecycle + streaming tests
```

**Frontend** (Node 18+):

```bash
cd frontend
npm install
npm run dev               # Vite dev server on :5173
```

### Run the live demo (real sandbox + agent)

1. Start Docker (Desktop or `dockerd`) — the runtime pulls `python:3.11` on first run.
2. Give the agent credentials: `export ANTHROPIC_API_KEY=...` (or `ant auth login`).
3. In `.env`, set `AWS_RUNTIME_BACKEND=docker`.
4. `make dev` (backend) and `npm run dev` (frontend), then open http://localhost:5173,
   enter a task + a public repo, and hit **Launch**. Watch the planes light up and the
   agent's commands stream into the terminal.

No Docker or key handy? Set `AWS_RUNTIME_BACKEND=mock` — the whole flow (launch →
stream → teardown) still runs; the execution plane just emits a canned trace.

## How to use this template

1. Start in `models.py` — the domain vocabulary everything else speaks.
2. Read `orchestrator.py` to see how a workspace is assembled and torn down.
3. Pick a plane and implement its `TODO:`s. Each plane exposes an abstract base
   class / Protocol so you can start with an in-memory or mock implementation and
   swap in a real one later.
4. Grep for `TODO:` to find every place that needs work:

   ```bash
   grep -rn "TODO:" src/
   ```

## Non-goals of the template

- It does not ship a hypervisor: the Docker runtime is hardened (caps dropped,
  no-new-privileges, cgroup limits) but still shares the host kernel. For
  hostile-by-design code, add a gVisor/Kata or microVM (Firecracker) backend.
- The secretless credential proxy is real but single-tenant: one shared proxy whose
  allowlist/credential map is set per run. Multi-tenant identity minting is next.
- Treat the `mock` security backend as insecure by definition — it enforces nothing.

## License

TODO: choose a license (MIT / Apache-2.0 / proprietary) and add a `LICENSE` file.
