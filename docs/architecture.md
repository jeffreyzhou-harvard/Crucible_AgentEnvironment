# Architecture

This is the architecture of **Crucible**: sandbox environments where
autonomous agents safely execute code, interact with services, and verify their own
work. The design refuses the usual trade-off between **fidelity**, **isolation**,
and **speed** — it pushes on all of them at once by splitting concerns into four
planes plus a cross-cutting trace layer.

## Why planes

Each plane has one job and one thing it optimizes for. They meet only through narrow
interfaces (an abstract base class per plane), so any plane can be implemented,
tested, and replaced independently. The `Orchestrator` is the only place that knows
about all four, and it depends on their interfaces — never their implementations.

```
                         ┌──────────────────────────┐
        HTTP  ─────────▶ │      api / main          │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │       Orchestrator        │
                         └──┬─────┬─────┬─────┬───┬──┘
             control ◀──────┘     │     │     │   └──────▶ trace
           (speed)          data  │     │  execution
                       (reproduce)│     │  (fidelity)
                                   │  security
                                   │ (isolation)
```

## The four planes

### Control (speed) — `control/`
Warm pools of pre-provisioned sandboxes, a demand-predicting scheduler, and intent
prediction that begins provisioning while the user is still typing. Turns a
multi-second cold start into an instant attach.
- `scheduler.py` — `acquire`/`release`; fast path (warm) vs. cold path (provision)
- `warm_pool.py` — bounded hot pool, refill loop, LRU eviction
- `intent.py` — speculative provisioning from early signals

### Execution (fidelity) — `execution/`
A complete developer workstation: writable filesystem, cloned repos, Docker,
tooling, MCP servers. A trajectory that works here must work in production.
- `sandbox.py` — `attach`/`run_agent`/`destroy`
- `runtime.py` — pluggable backend (docker / firecracker / k8s)
- `filesystem.py` — writable tree + repo clone
- `mcp.py` — MCP servers + dev tooling

### Security & Network (isolation) — `security/`
Broad capability without exfiltration or escape.
- `credential_proxy.py` — secretless architecture; secrets never enter the sandbox
- `network_policy.py` — ingress allowlist, egress control
- `isolation.py` — kernel/hardware isolation; composes the above into `secure()`

### Data (reproducibility) — `data/`
Every run starts from an identical, representative data state and mutates it safely.
- `provisioner.py` — `branch`/`teardown`
- `branching.py` — copy-on-write branch off a read-only reference snapshot
- `health.py` — verify readiness before handoff

### Trace (observability) — `trace/`
The sandbox is ephemeral; its trajectory is not. Every run is recorded to durable
storage outside the sandbox for replay, debugging, and evaluation.

## Lifecycle ordering (and why it matters)

`Orchestrator.create_workspace` runs the planes in a deliberate order:

1. **control** — claim/provision a sandbox
2. **trace** — open the trajectory before anything runs inside
3. **data** — branch datasets from the read-only snapshot
4. **security** — attach the credential proxy + network policy **before the agent**
5. **execution** — mount repos/tooling and attach the agent

Steps 4-before-5 is a security property, not a style choice: no agent-controlled
code should run before isolation is live. Teardown reverses this and must run to
completion even on partial failure — a leaked sandbox, data branch, proxy identity,
or firewall rule is an incident.

## Streaming lifecycle

The API is streaming-first so the frontend can watch a run unfold:

- `POST /v1/workspaces:launch` → `Orchestrator.begin()` mints ids and opens the trace,
  returns `{workspace_id, trace_id}` immediately, and schedules `run_lifecycle()` in the
  background.
- `run_lifecycle()` walks the planes in order and emits a `TraceEvent` at each step
  (`plane.control` → `plane.data` → `plane.security` → `plane.execution` → agent events
  → `workspace.end`), publishing each to the in-process `TraceBus`.
- `WS /v1/traces/{trace_id}/stream` subscribes: the bus atomically replays the history
  so far and then streams live events, so a client sees the whole trajectory whether it
  connects before, during, or after the run — no gaps, no duplicates.

## What's real vs. what's next

Real today, selected in `main.py:build_orchestrator` from settings:

- **Execution** — Docker container + Claude `bash`-tool agent loop, hardened
  (all caps dropped, no-new-privileges, cgroup limits).
- **Control** — runtime-backed warm pool with a refill loop started at app
  lifespan, EWMA demand predictor, shape-keyed claims, intent-driven speculative
  warming (`POST /v1/intent:signal`), stats at `GET /v1/pool`. The trace records
  `warm_hit` + `acquire_ms` per run.
- **Data** (`AWS_DATA_BRANCH_BACKEND=cow`) — copy-on-write branches via APFS
  clonefile / Linux reflink, content-hash receipts verified against the reference
  snapshot by the health checker before the agent runs; missing snapshots fail loudly.
- **Security** (`AWS_SECURITY_BACKEND=proxy`) — secretless egress proxy with
  allowlist + credential injection + audit; the experiment's `web_fetch` broker
  performs real policy-gated fetches.
- **Trace** — live stream always; durable JSONL store + `GET /v1/traces/{id}`
  replay when `AWS_TRACE_STORE_URI` is set.

Next frontier (the remaining `TODO:`s): microVM/gVisor runtime backends, Neon/ZFS
data backends, per-candidate proxy instances, multi-tenant quotas and identity.

```bash
make todos      # or: grep -rn "TODO:" src/
```
