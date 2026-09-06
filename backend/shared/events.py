import asyncio


class ChangeEventBus:
    """进程内数据变更广播总线：每个订阅者一条有界队列。

    事件是"某模块有变化，去重拉"的失效信号而非数据本身，订阅者积压时
    丢弃最旧的也不影响正确性，因此队列满时丢最旧、永不阻塞发布方。
    """

    def __init__(self, queue_size: int = 64) -> None:
        self._queue_size = queue_size
        self._subscribers: set[asyncio.Queue[dict[str, str]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, str]]:
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, str]]) -> None:
        self._subscribers.discard(queue)

    def publish(self, scope: str, action: str) -> None:
        if not self._subscribers:
            return
        event = {"type": "changed", "scope": scope, "action": action}
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)
