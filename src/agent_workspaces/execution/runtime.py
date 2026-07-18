"""RuntimeBackend — the pluggable container/VM layer beneath the sandbox.

This is the seam between "a Sandbox handle" and "a real, running, isolated
environment". The security plane's isolation guarantees ultimately depend on which
backend you choose here, so pick deliberately.
"""

from __future__ import annotations

import abc
import asyncio
from typing import Any

from ..config import Settings


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


class DockerBackend(RuntimeBackend):
    """Runs each sandbox as a Docker container.

    Fast to build; the WEAKEST isolation of the realistic options — a container
    shares the host kernel. For the hackathon MVP this is the credibility anchor
    (real code runs in a real box); before running untrusted agent code in
    production, pair it with strong host-level isolation (rootless/sysbox/gVisor)
    or move to a microVM backend (Firecracker). See security/isolation.py.

    The docker SDK is synchronous, so every call is pushed to a worker thread to
    keep the event loop responsive.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        import docker  # lazy: only needed when runtime_backend == "docker"

        self._docker = docker
        self.client = docker.from_env()

    async def restore_from_snapshot(self, base_image: str, network: str | None = None) -> str:
        net = network or self.settings.sandbox_network

        def _run() -> str:
            try:
                self.client.images.get(base_image)
            except self._docker.errors.ImageNotFound:
                # Cold start on a missing image. TODO: pre-pull into the warm pool
                # so this latency never lands on the request path.
                self.client.images.pull(base_image)
            container = self.client.containers.run(
                base_image,
                command=["sleep", "infinity"],  # keep it alive; we exec into it
                detach=True,
                working_dir=self.settings.sandbox_workdir,
                network_mode=net,  # per-call override; "none" for experiments = deny-all
                environment=self._proxy_env(),
                extra_hosts=self._extra_hosts(),
                # TODO (security plane): drop capabilities, read-only rootfs where
                # possible, cgroup limits, non-root user, seccomp/AppArmor profile.
            )
            container.exec_run(["mkdir", "-p", self.settings.sandbox_workdir])
            return str(container.id)

        return await asyncio.to_thread(_run)

    def _proxy_env(self) -> dict[str, str]:
        """When the proxy security plane is active, force ALL container egress
        through the host's egress proxy so the allowlist can't be bypassed."""
        if self.settings.security_backend != "proxy":
            return {}
        proxy_url = f"http://host.docker.internal:{self.settings.egress_proxy_port}"
        return {
            "HTTP_PROXY": proxy_url,
            "HTTPS_PROXY": proxy_url,
            "http_proxy": proxy_url,
            "https_proxy": proxy_url,
            "NO_PROXY": "localhost,127.0.0.1",
            "no_proxy": "localhost,127.0.0.1",
        }

    def _extra_hosts(self) -> dict[str, str] | None:
        """Make the host reachable from inside the container as host.docker.internal
        (needed on Linux, where it isn't provided automatically)."""
        if self.settings.security_backend != "proxy":
            return None
        return {"host.docker.internal": "host-gateway"}

    async def write_file(self, runtime_ref: str, path: str, content: str) -> None:
        """Write a file into the container without a bind mount or a shell heredoc
        (base64 round-trip avoids all quoting pitfalls)."""
        import base64

        encoded = base64.b64encode(content.encode()).decode()

        def _write() -> None:
            container = self.client.containers.get(runtime_ref)
            container.exec_run(
                ["sh", "-lc", f"echo {encoded} | base64 -d > {path}"],
                workdir=self.settings.sandbox_workdir,
            )

        await asyncio.to_thread(_write)

    async def exec(self, runtime_ref: str, argv: list[str]) -> tuple[int, bytes, bytes]:
        def _exec() -> tuple[int, bytes, bytes]:
            container = self.client.containers.get(runtime_ref)
            result: Any = container.exec_run(
                argv, demux=True, workdir=self.settings.sandbox_workdir
            )
            out, err = result.output if isinstance(result.output, tuple) else (result.output, None)
            code = result.exit_code if result.exit_code is not None else -1
            return code, out or b"", err or b""

        return await asyncio.to_thread(_exec)

    async def destroy(self, runtime_ref: str) -> None:
        def _rm() -> None:
            try:
                self.client.containers.get(runtime_ref).remove(force=True)
            except self._docker.errors.NotFound:
                pass  # already gone — teardown must be idempotent

        await asyncio.to_thread(_rm)


# TODO: stronger-isolation backends, selected via settings.runtime_backend.
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
