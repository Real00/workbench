from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass(frozen=True)
class ParsePayload:
    """平台传给插件的一次解析输入。"""

    url: str
    body: str
    config: dict[str, Any]


@dataclass
class ParsedArticle:
    """插件输出的文章。content_format 为 markdown 或 html。"""

    external_id: str
    title: str
    content: str = ""
    content_format: str = "html"
    published_at: str | None = None
    author: str = ""
    cover_url: str | None = None
    url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> ParsedArticle:
        allowed = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in allowed})


class SubscriptionParser(ABC):
    """所有订阅解析插件须继承此类，并实现 parse。

    不要在插件内发起 HTTP；平台已将源 URL 的响应放在 payload.body。
    """

    @abstractmethod
    def parse(self, payload: ParsePayload) -> list[ParsedArticle]:
        raise NotImplementedError
