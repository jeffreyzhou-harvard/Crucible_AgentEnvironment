"""Application settings.

Loaded from environment variables / `.env` (see `.env.example`). All settings are
prefixed with ``AWS_`` (Agent WorkspaceS). Access the singleton via ``get_settings()``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AWS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    env: Literal["local", "staging", "prod"] = "local"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # --- Control plane ---
    warm_pool_min_size: int = 2
    warm_pool_max_size: int = 16
    warm_pool_idle_ttl_seconds: int = 900

    # --- Execution plane ---
    runtime_backend: Literal["mock", "docker", "firecracker", "k8s"] = "mock"
    sandbox_base_image: str = "python:3.11"  # pullable default so the docker backend works OOTB
    sandbox_max_lifetime_seconds: int = 3600
    sandbox_workdir: str = "/workspace"
    # Docker network for the sandbox container. "bridge" = normal egress (MVP default).
    # TODO: the security plane should replace this with an isolated network + egress proxy.
    sandbox_network: str = "bridge"

    # --- Agent loop (Claude) ---
    anthropic_model: str = "claude-opus-4-8"
    agent_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    agent_max_iterations: int = 25
    agent_max_output_tokens: int = 8192

    # --- Experiments (fan-out best-of-N) ---
    experiment_candidates: int = 4          # how many candidates race per experiment
    experiment_redteam: int = 1             # how many are adversarial (probe the controls)
    # Force the scripted (no Docker / no API key) experiment path regardless of backend.
    experiment_scripted: bool = False
    experiment_step_delay: float = 0.35     # scripted pacing (seconds between beats)

    # --- Security & network plane ---
    # "mock" logs intent and enforces nothing; "proxy" runs a real secretless egress
    # proxy that allowlists destinations and injects credentials on the way out.
    security_backend: Literal["mock", "proxy"] = "mock"
    credential_proxy_url: str = "http://localhost:8081"
    egress_allowlist: str = ""  # comma-separated; parse via `egress_hosts`
    ingress_allowlist: str = ""
    # Where the egress proxy binds. 0.0.0.0 so sandbox containers can reach it via
    # the host gateway. The advertised URL is `credential_proxy_url` above.
    egress_proxy_host: str = "0.0.0.0"
    egress_proxy_port: int = 8081
    # Append-only JSONL audit of every allow/block decision. Empty = in-memory only.
    egress_audit_log: str = ""
    # Credentials injected at egress, keyed by host: "host=token,host2=token2".
    # These live ONLY in the proxy (control plane); they never enter the sandbox.
    proxy_credential_map: str = ""

    # --- Data plane ---
    dataset_snapshot_uri: str = ""
    data_branch_backend: Literal["mock", "zfs", "neon", "cow"] = "mock"

    # --- Trace store ---
    trace_store_uri: str = ""

    @property
    def egress_hosts(self) -> list[str]:
        return [h.strip() for h in self.egress_allowlist.split(",") if h.strip()]

    @property
    def ingress_hosts(self) -> list[str]:
        return [h.strip() for h in self.ingress_allowlist.split(",") if h.strip()]

    @property
    def proxy_credentials(self) -> dict[str, str]:
        """Parse `proxy_credential_map` ("host=token,...") into {host: token}."""
        creds: dict[str, str] = {}
        for pair in self.proxy_credential_map.split(","):
            host, sep, token = pair.partition("=")
            if sep and host.strip() and token.strip():
                creds[host.strip().lower()] = token.strip()
        return creds


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    TODO: for multi-tenant deployments, settings may need to be per-tenant rather
    than a process singleton. Revisit when tenancy is introduced.
    """
    return Settings()  # type: ignore[call-arg]  # values come from env
