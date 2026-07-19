"""The experiment's web_fetch broker: policy-gated, size-capped, real."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from agent_workspaces.experiment.docker_runner import _broker_fetch
from agent_workspaces.security.policy import decide


@pytest.fixture
def local_origin():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = b"hello from origin"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


async def test_allowed_fetch_returns_real_content(local_origin: str) -> None:
    # Policy allows the host, so the broker actually performs the fetch.
    decision = decide(f"{local_origin}/data", ["127.0.0.1"])
    assert decision.allowed is True

    content, is_error = await _broker_fetch(f"{local_origin}/data")
    assert is_error is False
    assert "200" in content
    assert "hello from origin" in content


async def test_denied_host_never_reaches_the_broker() -> None:
    # The deny decision happens in policy, before any fetch: no socket is opened.
    decision = decide("https://evil.example.com/exfil", ["github.com"])
    assert decision.allowed is False
    assert decision.host == "evil.example.com"


async def test_broker_rejects_non_http_schemes() -> None:
    content, is_error = await _broker_fetch("file:///etc/passwd")
    assert is_error is True
    assert "unsupported URL scheme" in content


async def test_broker_reports_unreachable_upstream() -> None:
    content, is_error = await _broker_fetch("http://127.0.0.1:1/nope")
    assert is_error is True
    assert "fetch failed" in content
