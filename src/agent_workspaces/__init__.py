"""Crucible — sandbox environments where AI agents safely act.

The package is organized into four planes plus a cross-cutting trace concern:

    control/    speed          — warm pools, scheduler, intent prediction
    execution/  fidelity       — sandbox runtime, filesystem, MCP servers
    security/   isolation      — credential proxy, network policy, isolation
    data/       reproducibility— dataset provisioning, branching, health
    trace/      observability  — record/replay execution trajectories

`orchestrator.Orchestrator` composes the planes into a single workspace lifecycle.
"""

__version__ = "0.1.0"
