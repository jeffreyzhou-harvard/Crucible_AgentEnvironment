"""Shared egress policy — the single allow/deny rule used across the codebase.

Both the live egress proxy (single-run path) and the best-of-N experiment consult
this so there is ONE definition of "is this host allowed" and ONE decision/record
shape (`EgressDecision`). Keeps the two features from drifting into two policies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlparse

from .audit import EgressDecision


def host_allowed(host: str, allowlist: Iterable[str]) -> bool:
    """True if `host` is on the allowlist (exact match or a subdomain of an entry).

    This is the single allow/deny rule: `EgressProxy.policy_for` (single-run) and the
    experiment fan-out both call it, so there is one definition and no drift.
    """
    h = (host or "").strip().lower()
    allow = {a.strip().lower() for a in allowlist if a.strip()}
    return h in allow or any(h.endswith("." + a) for a in allow)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def decide(url: str, allowlist: Iterable[str], *, sandbox_id: str | None = None) -> EgressDecision:
    """Build an `EgressDecision` for an outbound URL against the allowlist."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    allowed = host_allowed(host, allowlist)
    return EgressDecision(
        ts=now_iso(),
        method="GET",
        host=host,
        path=parsed.path or "/",
        allowed=allowed,
        reason="on egress allowlist" if allowed else "not on egress allowlist",
        credential_injected=False,
        sandbox_id=sandbox_id,
    )
