from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

PollFn = Callable[[], Awaitable[list]]


class SubscriptionScheduler:
    """进程内轮询：定期刷新到期的订阅源。"""

    def __init__(
        self,
        poll: PollFn,
        *,
        interval_seconds: float = 60.0,
        enabled: bool = True,
    ):
        self.poll = poll
        self.interval_seconds = interval_seconds
        self.enabled = enabled
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if not self.enabled or self._task is not None:
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop(), name="subscription-scheduler")

    async def stop(self) -> None:
        self._stopping.set()
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.poll()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("subscription scheduler tick failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self.interval_seconds
                )
                return
            except TimeoutError:
                continue
