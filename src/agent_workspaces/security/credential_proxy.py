"""Credential proxy — the secretless architecture.

The core rule: **secrets never enter the sandbox.** When the agent needs to call an
authenticated service, its request is routed through an external proxy that injects
the credential on the way out. The sandbox holds a short-lived, scoped handle at
most — never the real secret. Even a fully compromised sandbox has nothing to steal.
"""

from __future__ import annotations

import abc

from ..config import Settings
from ..models import Sandbox
from .proxy_server import EgressProxy


class CredentialProxy(abc.ABC):
    """Brokers authenticated egress on behalf of a sandbox without exposing secrets."""

    @abc.abstractmethod
    async def attach(self, sandbox: Sandbox) -> str:
        """Wire the sandbox to the proxy for the duration of a run.

        Returns the proxy endpoint the sandbox is configured to route through.

        TODO:
          - mint a per-sandbox, per-run identity (NOT a shared secret)
          - configure the sandbox's outbound path (HTTP(S)_PROXY / transparent route)
            so authenticated calls transit the proxy and get credentials injected there
          - scope what this sandbox is allowed to authenticate to (least privilege)
        """

    @abc.abstractmethod
    async def detach(self, sandbox: Sandbox) -> None:
        """Revoke the sandbox's proxy identity. Must survive partial failures."""


class MockCredentialProxy(CredentialProxy):
    """Returns the configured proxy URL; injects nothing. NOT secure."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def attach(self, sandbox: Sandbox) -> str:
        # TODO: real implementation mints an identity and configures routing.
        return self.settings.credential_proxy_url

    async def detach(self, sandbox: Sandbox) -> None:
        return None


class HttpCredentialProxy(CredentialProxy):
    """Real, proxy-backed credential broker.

    Owns a shared :class:`EgressProxy`. ``attach`` ensures it is running, loads the
    credential map (host -> token) that the proxy injects at egress, and marks this
    sandbox as the active identity. The secret is attached to outbound requests by
    the proxy and never enters the sandbox, so a fully compromised sandbox has
    nothing to steal.
    """

    def __init__(self, settings: Settings, proxy: EgressProxy) -> None:
        self.settings = settings
        self.proxy = proxy

    async def attach(self, sandbox: Sandbox) -> str:
        url = self.proxy.start()
        self.proxy.set_credentials(self.settings.proxy_credentials)
        self.proxy.set_active_sandbox(sandbox.id)
        return url

    async def detach(self, sandbox: Sandbox) -> None:
        # Revoke this sandbox's identity. The shared proxy keeps running for the
        # next run; it is stopped on application shutdown.
        self.proxy.set_active_sandbox(None)
