import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from ai_settings.jev import JevConnectionSettings, JevOptions
from progress.ai_tools import progress_ai_contribution
from pulse.agent import ALWAYS_AVAILABLE_TOOLS
from pulse.tool_router import JevCircuitBreaker, preload_tools
from shared.jev import JevTimeoutError

SETTINGS = JevConnectionSettings("https://example.test/v1", "jev-latest", "secret")


@pytest.fixture
def clock(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("pulse.tool_router.monotonic", lambda: now[0])
    return now


async def route(breaker, settings=SETTINGS):
    return await preload_tools(
        settings,
        [progress_ai_contribution()],
        ALWAYS_AVAILABLE_TOOLS,
        "创建任务",
        [],
        breaker=breaker,
    )


async def test_three_timeouts_skip_requests_then_successful_probe_recovers(monkeypatch, clock):
    evaluate = AsyncMock(side_effect=JevTimeoutError("timeout"))
    monkeypatch.setattr("pulse.tool_router.evaluate_tools", evaluate)
    breaker = JevCircuitBreaker()
    for _ in range(5):
        assert await route(breaker) == set()
    assert evaluate.await_count == 3
    clock[0] += 60
    evaluate.side_effect = None
    evaluate.return_value = {"create_task": 0.99}
    assert await route(breaker) == {"create_task"}
    assert await route(breaker) == {"create_task"}
    assert evaluate.await_count == 5
    assert breaker.timeouts == 0 and breaker.open_until == 0


@pytest.mark.parametrize("outcome", ["success", "error"])
def test_only_consecutive_timeouts_trip(clock, outcome):
    breaker = JevCircuitBreaker()
    for result in ["timeout", "timeout", outcome, "timeout", "timeout"]:
        ticket = breaker.acquire(SETTINGS)
        assert ticket is not None
        breaker.finish(ticket, result)
    assert breaker.acquire(SETTINGS) is not None


async def test_only_one_probe_and_failure_reopens(monkeypatch, clock):
    breaker = JevCircuitBreaker()
    for _ in range(3):
        breaker.finish(breaker.acquire(SETTINGS), "timeout")
    clock[0] += 60
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_probe(*args):
        started.set()
        await release.wait()
        raise JevTimeoutError("timeout")

    evaluate = AsyncMock(side_effect=slow_probe)
    monkeypatch.setattr("pulse.tool_router.evaluate_tools", evaluate)
    task = asyncio.create_task(route(breaker))
    await started.wait()
    assert await route(breaker) == set()
    assert evaluate.await_count == 1
    release.set()
    assert await task == set()
    assert await route(breaker) == set()
    assert evaluate.await_count == 1
    assert breaker.open_until == clock[0] + 60


def test_late_success_cannot_close_tripped_circuit_or_new_config(clock):
    breaker = JevCircuitBreaker()
    tickets = [breaker.acquire(SETTINGS) for _ in range(4)]
    for ticket in tickets[:3]:
        breaker.finish(ticket, "timeout")
    breaker.finish(tickets[3], "success")
    assert breaker.acquire(SETTINGS) is None
    fresh = breaker.acquire(replace(SETTINGS, api_key="new-key"))
    assert fresh is not None
    breaker.finish(tickets[0], "timeout")
    assert breaker.timeouts == 0


async def test_cancelled_probe_does_not_lock_circuit(monkeypatch, clock):
    breaker = JevCircuitBreaker()
    for _ in range(3):
        breaker.finish(breaker.acquire(SETTINGS), "timeout")
    clock[0] += 60
    monkeypatch.setattr(
        "pulse.tool_router.evaluate_tools", AsyncMock(side_effect=asyncio.CancelledError)
    )
    with pytest.raises(asyncio.CancelledError):
        await route(breaker)
    assert breaker.acquire(SETTINGS) is not None
    await route(breaker, settings=None)
    assert breaker.timeouts == 0 and not breaker.probing


def test_config_rejects_more_than_five_seconds():
    with pytest.raises(ValueError):
        JevOptions(timeout_seconds=5.1)
