"""Shared test fixtures.

These build an orchestrator wired entirely from the mock plane implementations, so
the full lifecycle can be exercised with zero infrastructure. As you implement real
backends, add fixtures that swap them in behind the same interfaces.
"""

from __future__ import annotations

import pytest

from agent_workspaces.config import Settings, get_settings
from agent_workspaces.main import build_orchestrator
from agent_workspaces.models import DatasetSpec, RepoSpec, WorkspaceRequest
from agent_workspaces.orchestrator import Orchestrator


@pytest.fixture(autouse=True)
def _force_mock_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the suite hermetic and free: the module-level app reads the developer's
    `.env` (which may select the Docker runtime + a real API key). Force mock
    backends via env (precedence over `.env`) so tests never spin real containers
    or call the Anthropic API."""
    monkeypatch.setenv("AWS_RUNTIME_BACKEND", "mock")
    monkeypatch.setenv("AWS_SECURITY_BACKEND", "mock")
    monkeypatch.setenv("AWS_DATA_BRANCH_BACKEND", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return Settings(env="local", runtime_backend="mock", data_branch_backend="mock")


@pytest.fixture
def orchestrator(settings: Settings) -> Orchestrator:
    return build_orchestrator(settings)


@pytest.fixture
def sample_request() -> WorkspaceRequest:
    return WorkspaceRequest(
        agent_id="agent-under-test",
        task_prompt="Fix the failing test in the payments module.",
        repos=[RepoSpec(url="https://example.com/acme/payments.git", ref="main")],
        datasets=[DatasetSpec(name="app_db", kind="postgres")],
        extra_egress_hosts=["api.example.com"],
    )
