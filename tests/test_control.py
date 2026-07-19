"""Control plane tests: the warm pool is real, shape-aware, and observable."""

from __future__ import annotations

import asyncio

from agent_workspaces.config import Settings
from agent_workspaces.control.intent import IntentPredictor
from agent_workspaces.control.scheduler import DemandPredictor, InMemoryScheduler
from agent_workspaces.control.warm_pool import WarmPool
from agent_workspaces.models import WorkspaceRequest


def _settings(**overrides: object) -> Settings:
    defaults: dict = {
        "env": "local",
        "runtime_backend": "mock",
        "warm_pool_min_size": 2,
        "warm_pool_max_size": 4,
        "warm_pool_idle_ttl_seconds": 900,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _request(**overrides: object) -> WorkspaceRequest:
    defaults: dict = {"agent_id": "a", "task_prompt": "t"}
    defaults.update(overrides)
    return WorkspaceRequest(**defaults)


async def test_refill_loop_fills_pool_to_min_size() -> None:
    pool = WarmPool(_settings())
    task = asyncio.create_task(pool.run())
    try:
        for _ in range(50):
            if await pool.size() >= 2:
                break
            await asyncio.sleep(0.02)
        assert await pool.size() >= 2
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_claim_from_pool_is_a_warm_hit() -> None:
    settings = _settings()
    pool = WarmPool(settings)
    scheduler = InMemoryScheduler(warm_pool=pool, settings=settings)

    # Warm one sandbox, then acquire: must be the warm one, flagged warm_hit.
    assert await pool.ensure_warm() is True
    sandbox = await scheduler.acquire(_request())
    assert sandbox.warm_hit is True
    assert pool.hits == 1

    # Pool now empty: the next acquire is a cold start, not a warm hit.
    cold = await scheduler.acquire(_request())
    assert cold.warm_hit is False
    assert pool.misses == 1


async def test_claim_respects_request_shape() -> None:
    settings = _settings()
    pool = WarmPool(settings)
    assert await pool.ensure_warm("python:3.11") is True

    # A request for a different base image must NOT steal the warm sandbox —
    # an incompatible claim silently breaks fidelity.
    mismatched = await pool.claim(
        _request(scheduling_hints={"base_image": "node:20"})
    )
    assert mismatched is None
    assert await pool.size() == 1

    matched = await pool.claim(_request(scheduling_hints={"base_image": "python:3.11"}))
    assert matched is not None


async def test_idle_sandboxes_are_evicted_and_booted_ones_destroyed() -> None:
    destroyed: list[str] = []

    async def boot(image: str) -> str:
        return f"ref-{image}"

    async def destroy(ref: str) -> None:
        destroyed.append(ref)

    pool = WarmPool(
        _settings(warm_pool_idle_ttl_seconds=0), boot=boot, destroy=destroy
    )
    assert await pool.ensure_warm() is True
    await asyncio.sleep(0.01)
    await pool._evict_idle()
    assert await pool.size() == 0
    assert pool.evicted == 1
    assert destroyed == ["ref-python:3.11"]


async def test_ensure_warm_deduplicates_and_respects_capacity() -> None:
    pool = WarmPool(_settings(warm_pool_max_size=1))
    assert await pool.ensure_warm() is True
    # Same shape already warm -> no duplicate speculation.
    assert await pool.ensure_warm() is False
    # At capacity -> a different shape is also refused.
    assert await pool.ensure_warm("node:20") is False


async def test_intent_signal_warms_a_shaped_sandbox() -> None:
    settings = _settings()
    pool = WarmPool(settings)
    intent = IntentPredictor(warm_pool=pool, settings=settings)

    assert await intent.on_signal({"base_image": "python:3.11"}) is True
    assert await pool.size() == 1
    # Duplicate signal for the same shape is a no-op.
    assert await intent.on_signal({"base_image": "python:3.11"}) is False

    # The speculatively warmed sandbox is claimable by the real request.
    key = intent.shape_key(_request())
    assert key.startswith("python:3.11|")
    sandbox = await pool.claim(_request())
    assert sandbox is not None and sandbox.warm_hit is True


async def test_demand_predictor_scales_with_arrivals() -> None:
    predictor = DemandPredictor(_settings(), horizon_seconds=60, window_seconds=10)
    baseline = await predictor.predict()
    assert baseline == 2  # floor = warm_pool_min_size

    for _ in range(50):
        predictor.record_arrival()
    surged = await predictor.predict()
    assert surged > baseline


async def test_pool_stats_shape() -> None:
    pool = WarmPool(_settings())
    await pool.ensure_warm()
    await pool.claim(_request())
    stats = await pool.stats()
    assert stats["size"] == 0
    assert stats["hits"] == 1
    assert stats["provisioned"] == 1
    assert stats["hit_rate"] == 1.0
