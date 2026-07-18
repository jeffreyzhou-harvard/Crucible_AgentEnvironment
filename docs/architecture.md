# Architecture

This template implements the *agent workspaces* model: sandbox environments where
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

## Where to start implementing

Everything ships as a mock so the lifecycle and API run with no infrastructure.
Implement planes in whatever order matches your risk:

- **Correctness-first:** execution → data → trace → control → security
- **Safety-first:** security → execution → data → control → trace

Grep the TODOs for the full worklist:

```bash
make todos      # or: grep -rn "TODO:" src/
```
