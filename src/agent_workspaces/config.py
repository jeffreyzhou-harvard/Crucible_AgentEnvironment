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
    sandbox_base_image: str = "agent-workspace:base"
    sandbox_max_lifetime_seconds: int = 3600

    # --- Security & network plane ---
    credential_proxy_url: str = "http://localhost:8081"
    egress_allowlist: str = ""  # comma-separated; parse via `egress_hosts`
    ingress_allowlist: str = ""

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


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    TODO: for multi-tenant deployments, settings may need to be per-tenant rather
    than a process singleton. Revisit when tenancy is introduced.
    """
    return Settings()  # type: ignore[call-arg]  # values come from env
