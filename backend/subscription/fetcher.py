from __future__ import annotations

from dataclasses import dataclass

from aiohttp import ClientError, ClientSession, ClientTimeout

MAX_BODY_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class FetchResult:
    url: str
    body: str
    status: int
    content_type: str


class HttpFetcher:
    def __init__(self, *, timeout_seconds: float = 30.0, max_bytes: int = MAX_BODY_BYTES):
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    async def fetch(self, url: str, *, headers: dict[str, str] | None = None) -> FetchResult:
        timeout = ClientTimeout(total=self.timeout_seconds)
        request_headers = {
            "User-Agent": "WorkbenchSubscription/1.0",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        }
        if headers:
            request_headers.update(headers)
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=request_headers) as resp:
                    if resp.status >= 400:
                        text = await resp.text(errors="replace")
                        raise ValueError(f"HTTP {resp.status}: {text[:200]}")
                    raw = await resp.content.read(self.max_bytes + 1)
                    if len(raw) > self.max_bytes:
                        raise ValueError(f"响应超过 {self.max_bytes} 字节上限")
                    charset = resp.charset or "utf-8"
                    try:
                        body = raw.decode(charset)
                    except LookupError:
                        body = raw.decode("utf-8", errors="replace")
                    except UnicodeDecodeError:
                        body = raw.decode("utf-8", errors="replace")
                    return FetchResult(
                        url=str(resp.url),
                        body=body,
                        status=resp.status,
                        content_type=resp.content_type or "",
                    )
        except TimeoutError as exc:
            raise ValueError("拉取订阅源超时") from exc
        except ClientError as exc:
            raise ValueError(f"无法连接订阅源：{exc}") from exc
