"""EgressProxy — the secretless forwarding proxy that enforces the security plane.

The sandbox is configured to route ALL outbound traffic through this proxy (via the
HTTP(S)_PROXY env vars set on the container). Because a proxied client hands the full
URL to the proxy instead of dialing the target itself, the proxy owns all routing —
so the allowlist is unbypassable from inside the box.

Two guarantees:
  * ALLOWLIST — a destination host not on the allowlist is dropped (HTTP 403, or a
    refused CONNECT for HTTPS). A compromised/prompt-injected agent cannot phone home.
  * INJECT    — for approved hosts, the real credential is attached on the way out, so
    the secret never has to live inside the sandbox.

Plain HTTP requests can have credentials injected. HTTPS is tunnelled via CONNECT;
the tunnel is opaque (TLS), so the allowlist is still enforced on the target host but
no credential can be injected inside it — by design.

This is the runnable core of security/{credential_proxy,network_policy}.py. It is a
single-tenant scaffold: one shared proxy whose active allowlist / credential map /
sandbox id are set by the security plane for the current run.
"""

from __future__ import annotations

import http.client
import json
import select
import socket
import threading
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterable, Mapping

from .audit import EgressAuditLog, EgressDecision
from .policy import host_allowed

# Hop-by-hop and client-supplied headers we refuse to forward upstream. We strip the
# client's Authorization too: the ONLY credential that goes out is the one we inject.
_STRIP = {
    "proxy-connection",
    "connection",
    "authorization",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EgressProxy:
    """A threaded HTTP/HTTPS forward proxy with an allowlist and credential injection."""

    def __init__(
        self,
        *,
        host: str = "0.0.0.0",
        port: int = 8081,
        audit: EgressAuditLog | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.audit = audit or EgressAuditLog()
        self._allowlist: set[str] = set()
        self._credentials: dict[str, str] = {}
        # Optional host -> (host, port) redirection. Lets tests/demos point a logical
        # name like "api.internal" at a loopback origin without editing /etc/hosts.
        self._host_overrides: dict[str, tuple[str, int]] = {}
        self._active_sandbox: str | None = None
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ---- policy configuration (set by the security plane per run) ---------------- #
    def set_allowlist(self, hosts: Iterable[str]) -> None:
        with self._lock:
            self._allowlist = {h.strip().lower() for h in hosts if h.strip()}

    def set_credentials(self, credentials: Mapping[str, str]) -> None:
        with self._lock:
            self._credentials = {k.lower(): v for k, v in credentials.items()}

    def set_host_overrides(self, overrides: Mapping[str, tuple[str, int]]) -> None:
        with self._lock:
            self._host_overrides = {k.lower(): v for k, v in overrides.items()}

    def set_active_sandbox(self, sandbox_id: str | None) -> None:
        with self._lock:
            self._active_sandbox = sandbox_id

    def policy_for(
        self, host: str | None
    ) -> tuple[bool, str | None, tuple[str, int] | None, str | None]:
        """Return (allowed, credential, backend_override, active_sandbox_id).

        Allow/deny is decided by the shared `security.policy.host_allowed`, so the
        proxy and the experiment fan-out use one definition of "is this host allowed".
        """
        key = (host or "").lower()
        with self._lock:
            allowlist = set(self._allowlist)
            credential = self._credentials.get(key)
            backend = self._host_overrides.get(key)
            sandbox = self._active_sandbox
        return host_allowed(key, allowlist), credential, backend, sandbox

    @property
    def url(self) -> str:
        display_host = "127.0.0.1" if self.host in ("0.0.0.0", "") else self.host
        return f"http://{display_host}:{self.port}"

    # ---- lifecycle -------------------------------------------------------------- #
    def start(self) -> str:
        with self._lock:
            if self._server is not None:
                return self.url

        handler = _make_handler(self)
        server = ThreadingHTTPServer((self.host, self.port), handler)
        # If bound with port 0 (ephemeral, used by tests), capture the real port.
        self.port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, name="egress-proxy", daemon=True)
        thread.start()
        with self._lock:
            self._server = server
            self._thread = thread
        return self.url

    def stop(self) -> None:
        with self._lock:
            server, self._server = self._server, None
            thread, self._thread = self._thread, None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)


def _make_handler(proxy: EgressProxy) -> type[BaseHTTPRequestHandler]:
    class ProxyHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _forward(self) -> None:
            parsed = urllib.parse.urlsplit(self.path)
            host = parsed.hostname
            port = parsed.port or 80
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query

            allowed, credential, backend, sandbox = proxy.policy_for(host)
            if not host or not allowed:
                proxy.audit.record(
                    EgressDecision(
                        ts=_now_iso(),
                        method=self.command,
                        host=host or "?",
                        path=parsed.path or "/",
                        allowed=False,
                        reason="not on egress allowlist",
                        sandbox_id=sandbox,
                    )
                )
                self._respond(403, {"error": f"egress to {host!r} denied by policy"})
                return

            body = self._read_body()
            headers = {k: v for k, v in self.headers.items() if k.lower() not in _STRIP}
            headers["Host"] = host if port == 80 else f"{host}:{port}"
            injected = False
            if credential:
                headers["Authorization"] = f"Bearer {credential}"  # injected here, last moment
                injected = True

            target_host, target_port = backend if backend else (host, port)
            try:
                conn = http.client.HTTPConnection(target_host, target_port, timeout=15)
                conn.request(self.command, path, body=body, headers=headers)
                upstream = conn.getresponse()
                data = upstream.read()
            except OSError as exc:
                proxy.audit.record(
                    EgressDecision(
                        ts=_now_iso(),
                        method=self.command,
                        host=host,
                        path=parsed.path or "/",
                        allowed=True,
                        reason=f"upstream error: {exc}",
                        credential_injected=injected,
                        sandbox_id=sandbox,
                    )
                )
                self._respond(502, {"error": "bad gateway"})
                return

            proxy.audit.record(
                EgressDecision(
                    ts=_now_iso(),
                    method=self.command,
                    host=host,
                    path=parsed.path or "/",
                    allowed=True,
                    reason="forwarded",
                    credential_injected=injected,
                    sandbox_id=sandbox,
                )
            )
            self.send_response(upstream.status)
            for key, value in upstream.getheaders():
                if key.lower() in _STRIP or key.lower() == "content-length":
                    continue
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = _forward
        do_POST = _forward
        do_PUT = _forward
        do_DELETE = _forward
        do_PATCH = _forward
        do_HEAD = _forward

        def do_CONNECT(self) -> None:  # noqa: N802 — HTTPS tunnel
            host, _, port_str = self.path.partition(":")
            port = int(port_str or 443)
            allowed, _cred, backend, sandbox = proxy.policy_for(host)
            if not allowed:
                proxy.audit.record(
                    EgressDecision(
                        ts=_now_iso(),
                        method="CONNECT",
                        host=host,
                        path="",
                        allowed=False,
                        reason="not on egress allowlist (https)",
                        sandbox_id=sandbox,
                    )
                )
                self._respond(403, {"error": f"egress to {host!r} denied by policy"})
                return

            target_host, target_port = backend if backend else (host, port)
            try:
                upstream = socket.create_connection((target_host, target_port), timeout=15)
            except OSError:
                self._respond(502, {"error": "bad gateway"})
                return

            proxy.audit.record(
                EgressDecision(
                    ts=_now_iso(),
                    method="CONNECT",
                    host=host,
                    path="",
                    allowed=True,
                    reason="tunnel opened (tls opaque — no credential injection)",
                    credential_injected=False,
                    sandbox_id=sandbox,
                )
            )
            self.send_response(200, "Connection Established")
            self.end_headers()
            self.close_connection = True
            self._tunnel(self.connection, upstream)

        def _tunnel(self, client: socket.socket, upstream: socket.socket) -> None:
            endpoints = [client, upstream]
            try:
                while True:
                    readable, _, _ = select.select(endpoints, [], [], 60)
                    if not readable:
                        break
                    for sock in readable:
                        other = upstream if sock is client else client
                        chunk = sock.recv(65536)
                        if not chunk:
                            return
                        other.sendall(chunk)
            except OSError:
                pass
            finally:
                for sock in (client, upstream):
                    try:
                        sock.close()
                    except OSError:
                        pass

        def _read_body(self) -> bytes | None:
            length = int(self.headers.get("Content-Length", 0) or 0)
            return self.rfile.read(length) if length else None

        def _respond(self, code: int, body: dict[str, Any]) -> None:
            payload = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def finish(self) -> None:
            # After a CONNECT tunnel the socket is already closed; don't let the
            # base handler's flush raise and spam the proxy thread with tracebacks.
            try:
                super().finish()
            except OSError:
                pass

        def log_message(self, *args: Any) -> None:
            return None

    return ProxyHandler
