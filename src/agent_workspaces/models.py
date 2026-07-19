"""Shared domain models — the vocabulary every plane speaks.

Start here. These types flow across the control, execution, security, and data
planes and into the trace store. Keep them serializable (they cross process and
network boundaries) and free of any plane-specific implementation detail.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Identifiers
# --------------------------------------------------------------------------- #
# TODO: consider typed NewType wrappers (WorkspaceId = NewType("WorkspaceId", str))
#       so the type checker stops you from passing a sandbox id where a workspace
#       id is expected. Left as plain str for now to keep the scaffold readable.
WorkspaceId = str
SandboxId = str
TraceId = str
SnapshotId = str


class SandboxState(str, Enum):
    """Lifecycle states of a sandbox as tracked by the control plane."""

    PROVISIONING = "provisioning"  # base snapshot restoring, services booting
    WARM = "warm"                  # ready in the pool, not yet claimed
    CLAIMED = "claimed"            # assigned to a workspace, agent attaching
    RUNNING = "running"            # agent actively executing
    DRAINING = "draining"          # agent done, flushing trace, tearing down
    DESTROYED = "destroyed"        # gone; only the trace remains
    FAILED = "failed"              # provisioning/health check failed


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class RepoSpec(BaseModel):
    """A repository to clone into the sandbox filesystem."""

    url: str
    ref: str = "main"  # branch, tag, or commit
    # TODO: how is read access authorized? Credentials must NOT be embedded here —
    #       they resolve through the credential proxy (security plane).


class DatasetSpec(BaseModel):
    """A dataset the data plane should make available before the agent starts."""

    name: str
    kind: str = Field(description="e.g. 'postgres', 'redis', 'analytical'")
    snapshot_id: SnapshotId | None = None  # None => use the configured default snapshot


class WorkspaceRequest(BaseModel):
    """What a caller asks for when they want a workspace.

    Produced by the API layer, consumed by the orchestrator + control plane.
    """

    agent_id: str
    task_prompt: str
    repos: list[RepoSpec] = Field(default_factory=list)
    datasets: list[DatasetSpec] = Field(default_factory=list)
    # Hosts the agent is allowed to reach, on top of the global egress allowlist.
    extra_egress_hosts: list[str] = Field(default_factory=list)
    # Free-form hints the control plane may use for warm-pool matching / prediction.
    scheduling_hints: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Live objects
# --------------------------------------------------------------------------- #
class Sandbox(BaseModel):
    """A single isolated execution environment.

    This is the *handle* the control plane hands around. The actual running
    environment lives behind the execution plane's runtime backend.
    """

    id: SandboxId
    state: SandboxState = SandboxState.PROVISIONING
    base_image: str
    created_at: datetime
    claimed_at: datetime | None = None
    # Opaque, backend-specific address the execution plane uses to attach
    # (e.g. a container id, a VM socket, a k8s pod name).
    runtime_ref: str | None = None


class Workspace(BaseModel):
    """A sandbox plus everything provisioned around it for one agent run."""

    id: WorkspaceId
    request: WorkspaceRequest
    sandbox: Sandbox
    trace_id: TraceId
    data_branch_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class ExecutionResult(BaseModel):
    """The outcome of running the agent inside a workspace."""

    workspace_id: WorkspaceId
    trace_id: TraceId
    exit_code: int
    succeeded: bool
    summary: str = ""
    artifacts: dict[str, str] = Field(default_factory=dict)  # name -> URI


class LaunchResponse(BaseModel):
    """Returned immediately from the launch endpoint so the client can open the
    trace stream while the agent runs in the background."""

    workspace_id: WorkspaceId
    trace_id: TraceId


# --------------------------------------------------------------------------- #
# Experiments (fan-out best-of-N)
# --------------------------------------------------------------------------- #
class ExperimentRequest(BaseModel):
    """Run one task N times in parallel, score each in its own sandbox, and rank.

    The atomic unit of a self-improvement loop: propose N solutions → test each in an
    isolated, reproducible workspace → validate against a held-out grader → select.
    """

    task_id: str = "devowel"  # which task in experiment/tasks.py
    candidates: int | None = None  # default: settings.experiment_candidates
    redteam: int | None = None  # how many adversarial candidates; default from settings
    rounds: int | None = None  # self-improvement rounds; each seeds the next from the winner


class ExperimentLaunchResponse(BaseModel):
    experiment_id: str
    trace_id: TraceId


class TraceEvent(BaseModel):
    """One recorded step in an execution trajectory (command, tool call, output)."""

    trace_id: TraceId
    ts: datetime
    kind: str  # e.g. "command", "tool_call", "network", "fs_write"
    payload: dict[str, Any] = Field(default_factory=dict)
