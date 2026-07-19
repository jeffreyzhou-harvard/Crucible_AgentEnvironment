"""Shape keys — "what must a sandbox provide to serve this request?"

The warm pool, the scheduler, and the intent predictor must all agree on this
key, or a speculatively warmed sandbox can never be claimed by the request it
was warmed for. Kept deliberately coarse (base image + dataset kinds) to get
pool hits, but precise enough that a claim never hands back an environment
that can't serve the request.
"""

from __future__ import annotations

from ..config import Settings
from ..models import Sandbox, WorkspaceRequest


def shape_key_for_request(request: WorkspaceRequest, settings: Settings) -> str:
    """Stable shape key for a request: base image + the dataset kinds it needs.

    The base image may be overridden per request via
    ``scheduling_hints["base_image"]``; everything else defaults from settings.
    """
    hint = request.scheduling_hints.get("base_image")
    image = str(hint) if hint else settings.sandbox_base_image
    kinds = ",".join(sorted({d.kind for d in request.datasets}))
    return f"{image}|{kinds}"


def shape_key_for_sandbox(sandbox: Sandbox) -> str:
    """Shape key a warm sandbox provides.

    Warm sandboxes are provisioned bare (no datasets attached — the data plane
    branches per run, after claim), so their dataset component is empty only in
    the sense that data attaches later; they can serve any dataset mix.
    """
    return f"{sandbox.base_image}|*"


def shapes_match(sandbox_key: str, request_key: str) -> bool:
    """A sandbox matches when its image matches; `*` datasets serve any mix."""
    s_image, _, s_data = sandbox_key.partition("|")
    r_image, _, r_data = request_key.partition("|")
    return s_image == r_image and (s_data == "*" or s_data == r_data)
