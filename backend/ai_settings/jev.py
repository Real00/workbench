"""Shared Jev configuration; persisted credentials are encrypted by the application."""

from dataclasses import dataclass
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

JEV_MAX_TIMEOUT_SECONDS = 5.0


class JevOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    enabled: bool = False
    base_url: str = "https://api.typesafe.ai/v1"
    model: str = "jev-latest"
    threshold: float = Field(default=0.8, ge=0.5, le=1, allow_inf_nan=False)
    timeout_seconds: float = Field(
        default=3, ge=0.1, le=JEV_MAX_TIMEOUT_SECONDS, allow_inf_nan=False
    )

    def validate_connection(self) -> None:
        url = urlsplit(self.base_url)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            raise ValueError("Jev Base URL 必须是有效的 http(s) API 地址")
        if url.query or url.fragment:
            raise ValueError("Jev Base URL 不能包含查询参数或片段")
        if not self.model:
            raise ValueError("请填写 Jev 模型名称")


class JevInput(JevOptions):
    api_key: str | None = None


@dataclass(frozen=True)
class JevConnectionSettings:
    base_url: str
    model: str
    api_key: str
    threshold: float = 0.8
    timeout_seconds: float = 3
