"""The "real" service the research agent depends on.

Stands in for an experiment-tracking / eval API that an autoresearch loop must
query to score its runs. It hands back data ONLY when the request carries the
right credential; otherwise it returns 401. It has no idea a proxy exists — from
its point of view it just sees an authenticated caller.

In production the credential lives in a secrets manager and is issued to the
proxy; here we hardcode the same literal in fake_api.py and proxy.py so the demo
runs with zero setup. The single point that matters: the AGENT never has it.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Shared only between the real service and the proxy that is trusted to call it.
# NOTE: this string appears in proxy.py too, and NOWHERE in agent.py.
SECRET = "sk-live-eval-ExperimentResults-8f3a2c"  # noqa: S105 (demo credential)

HOST, PORT = "127.0.0.1", 9000

_RESULTS = {
    "experiments": [
        {"id": "exp-041", "metric": "val_bpb", "score": 0.9182, "kept": True},
        {"id": "exp-042", "metric": "val_bpb", "score": 0.9310, "kept": False},
        {"id": "exp-043", "metric": "val_bpb", "score": 0.9037, "kept": True},
    ]
}


class Handler(BaseHTTPRequestHandler):
    def _authenticated(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {SECRET}"

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        if not self._authenticated():
            print("[api]   401  rejected an UNAUTHENTICATED request")
            self._send(401, {"error": "missing or invalid credential"})
            return
        print("[api]   200  returned experiment results (request was authenticated)")
        self._send(200, _RESULTS)

    def _send(self, code: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args) -> None:  # silence default access log
        return None


if __name__ == "__main__":
    print(f"[api]   real eval service listening on http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
