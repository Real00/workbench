"""Pulse 附件暂存：把用户粘贴的文件在「对话 → 确认写入」之间保留在进程内。

与会话历史一样不落库；过期或超量自动淘汰，确认时若已丢失则要求用户重新粘贴。
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import monotonic
from typing import Any
from uuid import uuid4

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENTS = 64
ATTACHMENT_TTL_SECONDS = 2 * 60 * 60


@dataclass(frozen=True)
class PulseAttachment:
    id: str
    filename: str
    size: int
    text: str
    data: bytes
    created_at: float

    def summary(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.filename, "size": self.size, "chars": len(self.text)}

    def slice(self, offset: int, limit: int) -> dict[str, Any]:
        start = max(0, offset)
        end = start + max(1, limit)
        return {
            "id": self.id,
            "name": self.filename,
            "offset": start,
            "total_chars": len(self.text),
            "text": self.text[start:end],
            "has_more": end < len(self.text),
        }


class AttachmentStore:
    def __init__(
        self,
        max_items: int = MAX_ATTACHMENTS,
        ttl_seconds: float = ATTACHMENT_TTL_SECONDS,
        clock: Callable[[], float] = monotonic,
    ):
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._items: OrderedDict[str, PulseAttachment] = OrderedDict()

    def _evict(self) -> None:
        now = self._clock()
        expired = [
            key for key, item in self._items.items() if now - item.created_at > self.ttl_seconds
        ]
        for key in expired:
            self._items.pop(key, None)
        while len(self._items) > self.max_items:
            self._items.popitem(last=False)

    def put(self, filename: str, data: bytes, text: str) -> PulseAttachment:
        item = PulseAttachment(
            id=uuid4().hex[:12],
            filename=filename,
            size=len(data),
            text=text,
            data=data,
            created_at=self._clock(),
        )
        self._items[item.id] = item
        self._evict()
        return item

    def get(self, attachment_id: str) -> PulseAttachment | None:
        self._evict()
        item = self._items.get(attachment_id)
        if item is not None:
            self._items.move_to_end(attachment_id)
        return item

    def resolve(self, attachment_ids: Sequence[str] | None) -> list[PulseAttachment]:
        resolved: list[PulseAttachment] = []
        for attachment_id in attachment_ids or []:
            item = self.get(attachment_id)
            if item is None:
                raise ValueError("附件已过期或不存在，请重新粘贴文件")
            resolved.append(item)
        return resolved
