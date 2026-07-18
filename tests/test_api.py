"""Smoke tests for the control-plane HTTP surface."""

from __future__ import annotations

from fastapi.testclient import TestClient

from agent_workspaces.main import app


def test_healthz() -> None:
    with TestClient(app) as client:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_execute_endpoint() -> None:
    payload = {
        "agent_id": "agent-1",
        "task_prompt": "do the thing",
        "repos": [],
        "datasets": [],
    }
    with TestClient(app) as client:
        resp = client.post("/v1/workspaces:execute", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["succeeded"] is True
        assert body["trace_id"].startswith("tr_")

    # TODO: add tests for auth/quota rejection once the API enforces them.
