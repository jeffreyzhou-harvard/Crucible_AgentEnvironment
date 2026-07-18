"""MCP servers + dev tooling wired into the sandbox.

Agents act through tools. In a high-fidelity workspace, those tools are the same
Model Context Protocol servers and CLIs an engineer would use — a language server,
a database client, a browser, the project's own build tooling — all reachable from
inside the sandbox.
"""

from __future__ import annotations

import abc

from ..models import Sandbox


class McpServerSpec(abc.ABC):
    """Describes one MCP server to run inside (or alongside) the sandbox."""

    name: str
    # TODO: transport (stdio vs. streamable-http), launch command, and which
    #       capabilities/tools it exposes to the agent.


class ToolingProvisioner(abc.ABC):
    """Installs dev tooling and starts MCP servers for a sandbox."""

    @abc.abstractmethod
    async def install_tooling(self, sandbox: Sandbox) -> None:
        """Ensure language runtimes, package managers, and CLIs are present.

        TODO: prefer baking common tooling into the base snapshot (fast, reproducible)
        and only installing task-specific extras here.
        """

    @abc.abstractmethod
    async def start_mcp_servers(self, sandbox: Sandbox, servers: list[McpServerSpec]) -> None:
        """Start the MCP servers the agent will call through.

        TODO: servers that reach external services must route through the credential
        proxy and respect the egress allowlist — an MCP server is an exfiltration
        path if it can make arbitrary outbound calls with real secrets.
        """
