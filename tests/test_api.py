"""Smoke tests for the control-plane HTTP + WebSocket surface (mock runtime)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from agent_workspaces.api.routes import get_app_settings
from agent_workspaces.config import Settings
from agent_workspaces.main import app


def test_healthz() -> None:
    with TestClient(app) as client:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_launch_and_stream_trace() -> None:
    payload = {
        "agent_id": "agent-1",
        "task_prompt": "do the thing",
        "repos": [],
        "datasets": [],
    }
    with TestClient(app) as client:
        resp = client.post("/v1/workspaces:launch", json=payload)
        assert resp.status_code == 200
        trace_id = resp.json()["trace_id"]
        assert trace_id.startswith("tr_")

        kinds: list[str] = []
        with client.websocket_connect(f"/v1/traces/{trace_id}/stream") as ws:
            while True:
                event = ws.receive_json()
                kinds.append(event["kind"])
                if event["kind"] == "workspace.end":
                    break

    # History replay + live tail delivers the whole trajectory, race-free.
    assert kinds[0] == "workspace.start"
    assert "plane.execution" in kinds
    assert "agent.start" in kinds
    assert kinds[-1] == "workspace.end"


def test_trace_replay_endpoint() -> None:
    payload = {"agent_id": "agent-1", "task_prompt": "replay me", "repos": [], "datasets": []}
    with TestClient(app) as client:
        trace_id = client.post("/v1/workspaces:launch", json=payload).json()["trace_id"]
        # Drain the stream so the lifecycle is finished before we replay it.
        with client.websocket_connect(f"/v1/traces/{trace_id}/stream") as ws:
            while ws.receive_json()["kind"] != "workspace.end":
                pass

        resp = client.get(f"/v1/traces/{trace_id}")
        assert resp.status_code == 200
        kinds = [e["kind"] for e in resp.json()["events"]]
        assert kinds[0] == "workspace.start"
        assert kinds[-1] == "workspace.end"
        # The control plane's speed receipt rides on the trace.
        control = next(e for e in resp.json()["events"] if e["kind"] == "plane.control")
        assert "warm_hit" in control["payload"]
        assert "acquire_ms" in control["payload"]

        assert client.get("/v1/traces/tr_missing").status_code == 404


def test_pool_stats_endpoint() -> None:
    with TestClient(app) as client:
        resp = client.get("/v1/pool")
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is True
        assert {"size", "hits", "misses", "warm"} <= set(body)


def test_intent_signal_warms_pool() -> None:
    with TestClient(app) as client:
        resp = client.post("/v1/intent:signal", json={"surface": "test"})
        assert resp.status_code == 200
        if resp.json()["warmed"]:  # refill loop may have beaten us to it
            assert client.get("/v1/pool").json()["size"] >= 1


def test_destroy_endpoint_is_idempotent() -> None:
    payload = {"agent_id": "agent-1", "task_prompt": "t", "repos": [], "datasets": []}
    with TestClient(app) as client:
        workspace_id = client.post("/v1/workspaces:launch", json=payload).json()["workspace_id"]
        resp = client.post(f"/v1/workspaces/{workspace_id}:destroy")
        assert resp.status_code == 200
        # Destroying it again (or a never-launched id) is a safe no-op.
        again = client.post(f"/v1/workspaces/{workspace_id}:destroy").json()
        assert again["destroyed"] is False
        ghost = client.post("/v1/workspaces/ws_ghost:destroy").json()
        assert ghost["destroyed"] is False


def test_launch_rejected_without_api_key_when_configured() -> None:
    """When an API key is configured, launch endpoints require the X-API-Key header."""
    app.dependency_overrides[get_app_settings] = lambda: Settings(api_key="s3cret")
    try:
        with TestClient(app) as client:
            payload = {"agent_id": "a", "task_prompt": "t", "repos": [], "datasets": []}

            # No key -> rejected.
            assert client.post("/v1/workspaces:launch", json=payload).status_code == 401
            # Wrong key -> rejected.
            bad = client.post(
                "/v1/workspaces:launch", json=payload, headers={"X-API-Key": "nope"}
            )
            assert bad.status_code == 401
            # Correct key -> accepted.
            ok = client.post(
                "/v1/workspaces:launch", json=payload, headers={"X-API-Key": "s3cret"}
            )
            assert ok.status_code == 200
            assert ok.json()["trace_id"].startswith("tr_")
    finally:
        app.dependency_overrides.clear()
