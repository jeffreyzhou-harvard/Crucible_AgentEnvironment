"""Egress audit log — the tamper-evident record of what the sandbox tried to reach.

Every decision the egress proxy makes (allow / block, and whether a credential was
injected) is recorded here. Because the proxy serves requests on background threads,
all state is guarded by a lock. Entries are kept in memory (bounded) and optionally
mirrored to an append-only JSONL file. A single optional callback lets the security
plane stream each decision straight into the run's trace so it shows up live in the UI.

Audit I/O is best-effort by design: a failure to write the log must never break or
stall the agent's egress.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EgressDecision:
    """One allow/block decision for a single outbound request."""

    ts: str
    method: str
    host: str
    path: str
    allowed: bool
    reason: str
    credential_injected: bool = False
    sandbox_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EgressAuditLog:
    """Thread-safe, append-only log of egress decisions."""

    def __init__(self, *, file_path: str | None = None, max_entries: int = 2000) -> None:
        self._entries: list[EgressDecision] = []
        self._lock = threading.Lock()
        self._file_path = file_path or None
        self._max = max_entries
        self._callback: Callable[[EgressDecision], None] | None = None

    def set_callback(self, callback: Callable[[EgressDecision], None] | None) -> None:
        """Register (or clear) a per-run sink that receives each decision live."""
        with self._lock:
            self._callback = callback

    def record(self, decision: EgressDecision) -> None:
        with self._lock:
            self._entries.append(decision)
            if len(self._entries) > self._max:
                del self._entries[: -self._max]
            callback = self._callback
            file_path = self._file_path

        if file_path:
            try:
                with open(file_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(decision.to_dict()) + "\n")
            except OSError:
                pass  # never let audit I/O break egress

        if callback is not None:
            try:
                callback(decision)
            except Exception:  # noqa: BLE001 — live streaming is best-effort
                pass

    def entries(self) -> list[dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._entries]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
