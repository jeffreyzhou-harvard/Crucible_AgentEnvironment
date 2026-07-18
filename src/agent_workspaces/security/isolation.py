"""SecurityPlane — kernel/hardware isolation + the plane's public interface.

Composes the credential proxy and network policy, and owns the isolation boundary
itself: containing the Docker daemon and privileged operations the execution plane
grants the agent, using kernel- and hardware-level mechanisms.
"""

from __future__ import annotations

import abc
import asyncio

from ..config import Settings
from ..models import Sandbox, WorkspaceRequest
from ..trace.tracer import Tracer
from .audit import EgressAuditLog, EgressDecision
from .credential_proxy import CredentialProxy, HttpCredentialProxy, MockCredentialProxy
from .network_policy import AllowlistNetworkPolicy, MockNetworkPolicy, NetworkPolicy
from .proxy_server import EgressProxy


class SecurityPlane(abc.ABC):
    """Locks a sandbox down before the agent runs; unwinds it afterwards."""

    @abc.abstractmethod
    async def secure(
        self, sandbox: Sandbox, request: WorkspaceRequest, tracer: Tracer | None = None
    ) -> None:
        """Apply every isolation guarantee. Called BEFORE the agent attaches.

        Ordering is a security property: proxy + network policy must be live before
        any agent-controlled code can execute. If a ``tracer`` is supplied, the plane
        may stream live security events (e.g. egress decisions) into the trace.
        """

    @abc.abstractmethod
    async def teardown(self, sandbox: Sandbox, tracer: Tracer | None = None) -> None:
        """Revoke identities and rules. Must run even if the run failed."""


class MockSecurityPlane(SecurityPlane):
    """Wires the mock proxy + network policy. Establishes NO real isolation."""

    def __init__(
        self,
        settings: Settings,
        credential_proxy: CredentialProxy | None = None,
        network_policy: NetworkPolicy | None = None,
    ) -> None:
        self.settings = settings
        self.credential_proxy = credential_proxy or MockCredentialProxy(settings)
        self.network_policy = network_policy or MockNetworkPolicy(settings)

    async def secure(
        self, sandbox: Sandbox, request: WorkspaceRequest, tracer: Tracer | None = None
    ) -> None:
        await self.credential_proxy.attach(sandbox)
        await self.network_policy.apply(sandbox, request)
        # TODO: establish the kernel/hardware isolation boundary here:
        #   - user namespaces + dropped capabilities + seccomp/AppArmor profile
        #   - contain the nested Docker daemon (rootless / sysbox / gVisor / microVM)
        #   - resource limits (cgroups) so one sandbox can't starve the host
        #   Which mechanisms apply depends on execution.runtime.RuntimeBackend.

    async def teardown(self, sandbox: Sandbox, tracer: Tracer | None = None) -> None:
        # Run both even if the first raises — a leaked proxy identity or firewall
        # rule is a security incident. Re-raise the first failure so it's surfaced.
        errors: list[Exception] = []
        for step in (self.network_policy.revoke(sandbox), self.credential_proxy.detach(sandbox)):
            try:
                await step
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
        if errors:
            raise errors[0]


class ProxyingSecurityPlane(SecurityPlane):
    """Real security plane: a secretless egress proxy with an allowlist + audit log.

    ``secure`` starts the proxy (if needed), installs the run's allowlist and
    credential map, and — when given a tracer — streams every egress decision into
    the trace so blocks/allows show up live in the UI. ``teardown`` revokes the
    sandbox's identity and denies all egress, running every step even on failure.

    The isolation boundary itself (namespaces, seccomp, microVM) is still delegated
    to the runtime backend; this plane owns the network + credential guarantees.
    """

    def __init__(
        self,
        settings: Settings,
        proxy: EgressProxy | None = None,
        audit: EgressAuditLog | None = None,
        credential_proxy: CredentialProxy | None = None,
        network_policy: NetworkPolicy | None = None,
    ) -> None:
        self.settings = settings
        self.audit = audit or EgressAuditLog(file_path=settings.egress_audit_log or None)
        self.proxy = proxy or EgressProxy(
            host=settings.egress_proxy_host,
            port=settings.egress_proxy_port,
            audit=self.audit,
        )
        self.credential_proxy = credential_proxy or HttpCredentialProxy(settings, self.proxy)
        self.network_policy = network_policy or AllowlistNetworkPolicy(settings, self.proxy)

    async def secure(
        self, sandbox: Sandbox, request: WorkspaceRequest, tracer: Tracer | None = None
    ) -> None:
        await self.credential_proxy.attach(sandbox)
        await self.network_policy.apply(sandbox, request)

        if tracer is not None:
            loop = asyncio.get_running_loop()

            def _stream(decision: EgressDecision) -> None:
                # Called from the proxy's worker thread — hop back onto the event loop.
                asyncio.run_coroutine_threadsafe(
                    tracer.emit("security.egress", **decision.to_dict()), loop
                )

            self.audit.set_callback(_stream)

    async def teardown(self, sandbox: Sandbox, tracer: Tracer | None = None) -> None:
        # Run-to-completion teardown: one failure must not skip the rest. Stop live
        # streaming first, then revoke both; re-raise the first failure so the
        # orchestrator can record it (a leaked rule/identity is an incident).
        self.audit.set_callback(None)
        errors: list[Exception] = []
        for step in (self.network_policy.revoke(sandbox), self.credential_proxy.detach(sandbox)):
            try:
                await step
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
        if errors:
            raise errors[0]

    def shutdown(self) -> None:
        """Stop the shared proxy. Call on application shutdown."""
        self.proxy.stop()
