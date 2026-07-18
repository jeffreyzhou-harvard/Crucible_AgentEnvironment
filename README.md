# agent-workspaces

A template for building **agent workspaces** — sandbox environments where autonomous
AI agents can safely execute code, interact with real services, and verify their own
work. Inspired by [NeoSigma's *Agent Workspaces*](https://neosigma.ai/blog/agent-workspaces).

> "An agent is only as capable as the environment it can safely act in."

This repo is a **scaffold**: the structure, interfaces, and domain models are in place,
and the actual behavior is marked with `TODO:` comments for you to fill in. Nothing
here provisions real infrastructure yet — it's a map, not the territory.

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
├── orchestrator.py    # ties the four planes into one lifecycle
├── main.py            # FastAPI app entrypoint
├── api/               # HTTP routes for the control-plane API
├── control/           # Control plane  — scheduler, warm pool, intent
├── execution/         # Execution plane — sandbox, runtime, filesystem, MCP
├── security/          # Security plane  — credential proxy, network, isolation
├── data/              # Data plane      — provisioner, branching, health
└── trace/             # Execution trace recorder / replay
```

## Getting started

```bash
# 1. Install (Python 3.11+)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env      # then edit

# 3. Run the control-plane API
make dev                  # uvicorn with reload

# 4. Run the tests (they document expected behavior; most are skipped stubs)
make test
```

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

- It does not ship a real sandbox runtime, hypervisor, or container escape hardening.
- It does not implement real secret management — the credential proxy is a stub.
- Treat every default as insecure until you've implemented the security plane.

## License

TODO: choose a license (MIT / Apache-2.0 / proprietary) and add a `LICENSE` file.
