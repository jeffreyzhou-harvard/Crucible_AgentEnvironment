"""Filesystem — writable working tree + repo cloning inside the sandbox.

A high-fidelity dev workstation needs a real, writable filesystem with the target
repositories checked out exactly as an engineer would have them.
"""

from __future__ import annotations

import abc

from ..models import RepoSpec, Sandbox


class Filesystem(abc.ABC):
    """Manages the sandbox's writable working tree."""

    @abc.abstractmethod
    async def clone(self, sandbox: Sandbox, repo: RepoSpec, dest: str) -> None:
        """Clone `repo` at its ref into `dest` inside the sandbox.

        TODO: authorization for private repos must come from the credential proxy —
        never inject a token into the sandbox's environment or git config.
        """

    @abc.abstractmethod
    async def write(self, sandbox: Sandbox, path: str, data: bytes) -> None:
        """Write a file into the sandbox filesystem (e.g. seed configs)."""

    @abc.abstractmethod
    async def snapshot(self, sandbox: Sandbox) -> str:
        """Capture the working tree so changes can be inspected / replayed.

        TODO: decide granularity — full tree vs. diff-against-base. The trace store
        (trace/recorder.py) likely wants the diff, not gigabytes of vendored deps.
        """
