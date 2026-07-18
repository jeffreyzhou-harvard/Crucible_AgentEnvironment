"""RuntimeBackend — the pluggable container/VM layer beneath the sandbox.

This is the seam between "a Sandbox handle" and "a real, running, isolated
environment". The security plane's isolation guarantees ultimately depend on which
backend you choose here, so pick deliberately.
"""

from __future__ import annotations

import abc

from ..config import Settings
from ..models import Sandbox


class RuntimeBackend(abc.ABC):
    """Boots, snapshots, and destroys the actual execution environment."""

    @abc.abstractmethod
    async def restore_from_snapshot(self, base_image: str) -> str:
        """Create a live environment from a versioned base snapshot.

        Returns an opaque `runtime_ref` (container id, VM socket, pod name) that the
        rest of the execution plane uses to interact with it. Deterministic restore
        from the same snapshot is what makes cold starts reproducible.
        """

    @abc.abstractmethod
    async def exec(self, runtime_ref: str, argv: list[str]) -> tuple[int, bytes, bytes]:
        """Run a command inside the environment; return (exit_code, stdout, stderr)."""

    @abc.abstractmethod
    async def destroy(self, runtime_ref: str) -> None:
        """Destroy the environment and reclaim its resources. Idempotent."""


# TODO: implement one or more of these backends and select via settings.runtime_backend.
#
# class DockerBackend(RuntimeBackend):
#     """Fast to build; weakest isolation. Support Docker-in-Docker for the agent.
#        Must be paired with strong host-level isolation (see security/isolation.py)."""
#
# class FirecrackerBackend(RuntimeBackend):
#     """microVMs: hardware-level isolation with near-container start times.
#        Strong default for untrusted agent code."""
#
# class KubernetesBackend(RuntimeBackend):
#     """Pod-per-sandbox; leans on gVisor/Kata + NetworkPolicy for isolation."""


class MockRuntimeBackend(RuntimeBackend):
    """Records calls but boots nothing. For tests and local lifecycle wiring."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def restore_from_snapshot(self, base_image: str) -> str:
        return f"mock://{base_image}"

    async def exec(self, runtime_ref: str, argv: list[str]) -> tuple[int, bytes, bytes]:
        return (0, b"", b"")

    async def destroy(self, runtime_ref: str) -> None:
        return None
