"""The star: a secretless egress proxy for the agent sandbox.

This is the security plane of an autoresearch sandbox, distilled. The agent runs
untrusted code for hours; it must reach the eval service but must never hold the
credential, and must not be able to phone home if it gets prompt-injected.

Every outbound request the agent makes is forced through this proxy (via the
HTTP_PROXY env var inside the box). The proxy does exactly two jobs:

  1. ALLOWLIST  — checks the destination host; anything not approved is dropped.
  2. INJECT     — attaches the real credential at the last moment, on the way out.

Why the allowlist is unbypassable from inside the box: when a client uses an HTTP
proxy it does not resolve or dial the target itself — it hands the whole URL to
the proxy, which owns all routing. The proxy IS the only route out, so the agent
cannot sneak around it.

This mirrors src/agent_workspaces/security/{credential_proxy,network_policy}.py.
"""

from __future__ import annotations

import http.client
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# The ONLY agent-side place the credential lives. Never leaves this process.
SECRET = "sk-live-eval-ExperimentResults-8f3a2c"  # noqa: S105 (demo credential)

HOST, PORT = "127.0.0.1", 8080

# Outbound egress allowlist. A compromised agent cannot reach anything else.
ALLOWLIST = {"api.internal"}

# Maps a logical hostname to its real backend address. Stands in for DNS /
# service discovery; keeps the demo on loopback with no /etc/hosts edits.
ROUTES = {
    "api.internal": ("127.0.0.1", 9000),     # the approved eval service
    "exfil.attacker": ("127.0.0.1", 9100),   # attacker sink (never actually reached)
}

# Hop-by-hop / client-supplied headers we refuse to forward upstream.
_STRIP = {"proxy-connection", "connection", "authorization", "host"}


class ProxyHandler(BaseHTTPRequestHandler):
    def _forward(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        host = parsed.hostname
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        if host not in ALLOWLIST:
            print(f"[proxy] BLOCK  {self.command} {host}{parsed.path}  -> not on egress allowlist")
            self._respond(403, {"error": f"egress to {host!r} denied by policy"})
            return

        body = self._read_body()
        headers = {k: v for k, v in self.headers.items() if k.lower() not in _STRIP}
        headers["Host"] = host
        headers["Authorization"] = f"Bearer {SECRET}"  # <-- injected here, last moment

        backend = ROUTES[host]
        try:
            conn = http.client.HTTPConnection(*backend, timeout=10)
            conn.request(self.command, path, body=body, headers=headers)
            upstream = conn.getresponse()
            data = upstream.read()
        except OSError as exc:
            print(f"[proxy] ERROR  upstream {host} unreachable: {exc}")
            self._respond(502, {"error": "bad gateway"})
            return

        print(f"[proxy] ALLOW  {self.command} {host}{parsed.path}  -> injected credential, forwarded")
        self.send_response(upstream.status)
        self.send_header("Content-Type", upstream.getheader("Content-Type", "application/json"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = _forward
    do_POST = _forward
    do_PUT = _forward
    do_DELETE = _forward

    def do_CONNECT(self) -> None:  # noqa: N802
        # HTTPS tunneling is intentionally unsupported: plain HTTP keeps every
        # allow/block decision legible in the demo log. (A real proxy would
        # terminate TLS or CONNECT-tunnel to allowlisted hosts only.)
        print("[proxy] BLOCK  CONNECT (HTTPS tunnel not permitted in this demo)")
        self.send_error(405, "CONNECT not supported")

    def _read_body(self) -> bytes | None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        return self.rfile.read(length) if length else None

    def _respond(self, code: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args) -> None:
        return None


if __name__ == "__main__":
    print(f"[proxy] secretless egress proxy on http://{HOST}:{PORT}  allow={sorted(ALLOWLIST)}")
    ThreadingHTTPServer((HOST, PORT), ProxyHandler).serve_forever()
