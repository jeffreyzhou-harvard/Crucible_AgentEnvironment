"""Network policy — ingress allowlist and egress control.

Isolation without crippling capability: the agent can reach the specific services
it needs and nothing else. Inbound is denied by default; outbound is constrained to
an allowlist so a compromised agent can't phone home or exfiltrate in bulk.
"""

from __future__ import annotations

import abc

from ..config import Settings
from ..models import Sandbox, WorkspaceRequest
from .proxy_server import EgressProxy


class NetworkPolicy(abc.ABC):
    """Applies and revokes per-sandbox network rules."""

    @abc.abstractmethod
    async def apply(self, sandbox: Sandbox, request: WorkspaceRequest) -> None:
        """Install ingress/egress rules for this sandbox.

        Effective egress = settings.egress_allowlist + request.extra_egress_hosts.
        Ingress defaults to deny-all (settings.ingress_allowlist is usually empty).

        TODO:
          - enforce at a layer the agent can't tamper with (host firewall, sidecar,
            or the runtime backend's network namespace — NOT in-sandbox iptables)
          - allowlist by resolved destination, and guard against DNS rebinding
          - decide policy for the credential proxy endpoint (must stay reachable)
        """

    @abc.abstractmethod
    async def revoke(self, sandbox: Sandbox) -> None:
        """Remove all network rules for the sandbox. Idempotent."""


class MockNetworkPolicy(NetworkPolicy):
    """Logs intent, enforces nothing. NOT secure."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def apply(self, sandbox: Sandbox, request: WorkspaceRequest) -> None:
        # effective = self.settings.egress_hosts + request.extra_egress_hosts
        # TODO: actually program the enforcement layer.
        return None

    async def revoke(self, sandbox: Sandbox) -> None:
        return None


class AllowlistNetworkPolicy(NetworkPolicy):
    """Programs the egress allowlist on the shared :class:`EgressProxy`.

    Enforcement lives in the proxy, which the sandbox cannot bypass (it is the box's
    only route out), rather than in-sandbox iptables the agent could tamper with.
    The effective allowlist is the global one plus any per-request extra hosts.
    """

    def __init__(self, settings: Settings, proxy: EgressProxy) -> None:
        self.settings = settings
        self.proxy = proxy

    async def apply(self, sandbox: Sandbox, request: WorkspaceRequest) -> None:
        effective = self.settings.egress_hosts + request.extra_egress_hosts
        self.proxy.set_allowlist(effective)

    async def revoke(self, sandbox: Sandbox) -> None:
        # Deny-all once the run is over. Idempotent.
        self.proxy.set_allowlist([])
