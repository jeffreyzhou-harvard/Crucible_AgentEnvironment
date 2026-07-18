"""SecurityPlane — kernel/hardware isolation + the plane's public interface.

Composes the credential proxy and network policy, and owns the isolation boundary
itself: containing the Docker daemon and privileged operations the execution plane
grants the agent, using kernel- and hardware-level mechanisms.
"""

from __future__ import annotations

import abc

from ..config import Settings
from ..models import Sandbox, WorkspaceRequest
from .credential_proxy import CredentialProxy, MockCredentialProxy
from .network_policy import MockNetworkPolicy, NetworkPolicy


class SecurityPlane(abc.ABC):
    """Locks a sandbox down before the agent runs; unwinds it afterwards."""

    @abc.abstractmethod
    async def secure(self, sandbox: Sandbox, request: WorkspaceRequest) -> None:
        """Apply every isolation guarantee. Called BEFORE the agent attaches.

        Ordering is a security property: proxy + network policy must be live before
        any agent-controlled code can execute.
        """

    @abc.abstractmethod
    async def teardown(self, sandbox: Sandbox) -> None:
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

    async def secure(self, sandbox: Sandbox, request: WorkspaceRequest) -> None:
        await self.credential_proxy.attach(sandbox)
        await self.network_policy.apply(sandbox, request)
        # TODO: establish the kernel/hardware isolation boundary here:
        #   - user namespaces + dropped capabilities + seccomp/AppArmor profile
        #   - contain the nested Docker daemon (rootless / sysbox / gVisor / microVM)
        #   - resource limits (cgroups) so one sandbox can't starve the host
        #   Which mechanisms apply depends on execution.runtime.RuntimeBackend.

    async def teardown(self, sandbox: Sandbox) -> None:
        # TODO: run both even if the first raises, and report failures — a leaked
        #       proxy identity or firewall rule is a security incident, not a warning.
        await self.network_policy.revoke(sandbox)
        await self.credential_proxy.detach(sandbox)
