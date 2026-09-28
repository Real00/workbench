from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import uuid4

CONTENT_FORMATS = frozenset({"markdown", "html"})
MIN_INTERVAL_MINUTES = 5
MAX_INTERVAL_MINUTES = 10080
MAX_SCRIPT_CHARS = 200_000
MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_URL_LENGTH = 2000
MAX_CONTENT_CHARS = 500_000
MAX_EXTERNAL_ID_LENGTH = 500
MAX_AUTHOR_LENGTH = 200
MAX_TITLE_LENGTH = 500
SOURCE_STATUSES = frozenset({"idle", "ok", "error", "running"})


def _now() -> datetime:
    return datetime.now(UTC)


def _require_http_url(value: str, *, field_name: str = "url") -> str:
    text = (value or "").strip()
    if not text or len(text) > MAX_URL_LENGTH:
        raise ValueError(f"{field_name} 无效")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} 必须是 http(s) 地址")
    return text


def _optional_http_url(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return _require_http_url(text, field_name=field_name)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid datetime: {value}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@dataclass
class Plugin:
    id: str
    name: str
    description: str
    script: str
    builtin: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        name: str,
        script: str,
        *,
        description: str = "",
        builtin: bool = False,
        ident: str | None = None,
    ) -> Plugin:
        plugin = cls(
            ident or str(uuid4()),
            "",
            "",
            "",
            builtin,
            _now(),
            _now(),
        )
        return plugin.apply(
            {"name": name, "description": description, "script": script},
            creating=True,
        )

    def apply(self, changes: dict[str, Any], *, creating: bool = False) -> Plugin:
        if (
            self.builtin
            and not creating
            and ("name" in changes or "script" in changes)
        ):
            raise ValueError("内置插件不可修改名称或脚本")
        name = self.name if "name" not in changes else str(changes["name"] or "").strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            raise ValueError("插件名称无效")
        description = (
            self.description
            if "description" not in changes
            else str(changes.get("description") or "").strip()
        )
        if len(description) > MAX_DESCRIPTION_LENGTH:
            raise ValueError("插件描述过长")
        script = self.script if "script" not in changes else str(changes.get("script") or "")
        validate_plugin_script(script)
        return replace(
            self,
            name=name,
            description=description,
            script=script,
            updated_at=_now(),
        )


def validate_plugin_script(script: str) -> None:
    text = script or ""
    if not text.strip():
        raise ValueError("插件脚本不能为空")
    if len(text) > MAX_SCRIPT_CHARS:
        raise ValueError("插件脚本过长")
    try:
        tree = ast.parse(text, filename="<plugin>")
    except SyntaxError as exc:
        raise ValueError(f"插件脚本语法错误: {exc.msg} (line {exc.lineno})") from exc
    class_names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if _base_name(base) == "SubscriptionParser":
                    class_names.append(node.name)
    if not class_names:
        raise ValueError("脚本须定义继承 SubscriptionParser 的类")
    if len(class_names) > 1:
        raise ValueError("脚本只能定义一个 SubscriptionParser 子类")


def _base_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


@dataclass
class Source:
    id: str
    name: str
    url: str
    plugin_id: str
    config: dict[str, Any]
    enabled: bool
    interval_minutes: int
    last_fetched_at: datetime | None
    last_status: str
    last_error: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, changes: dict[str, Any]) -> Source:
        source = cls(
            str(uuid4()),
            "",
            "",
            "",
            {},
            True,
            60,
            None,
            "idle",
            "",
            _now(),
            _now(),
        )
        return source.apply(changes, creating=True)

    def apply(self, changes: dict[str, Any], *, creating: bool = False) -> Source:
        name = self.name if "name" not in changes else str(changes["name"] or "").strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            raise ValueError("订阅源名称无效")
        url = self.url if "url" not in changes else _require_http_url(str(changes["url"] or ""))
        if creating and not url:
            raise ValueError("订阅源 URL 必填")
        if "plugin_id" in changes:
            plugin_id = str(changes["plugin_id"] or "").strip()
        else:
            plugin_id = self.plugin_id
        if not plugin_id:
            raise ValueError("请选择解析插件")
        config = self.config if "config" not in changes else dict(changes.get("config") or {})
        if not isinstance(config, dict):
            raise ValueError("config 必须是对象")
        enabled = self.enabled if "enabled" not in changes else bool(changes["enabled"])
        interval = (
            self.interval_minutes
            if "interval_minutes" not in changes
            else int(changes["interval_minutes"])
        )
        if interval < MIN_INTERVAL_MINUTES or interval > MAX_INTERVAL_MINUTES:
            raise ValueError(
                f"刷新间隔须在 {MIN_INTERVAL_MINUTES}–{MAX_INTERVAL_MINUTES} 分钟之间"
            )
        return replace(
            self,
            name=name,
            url=url,
            plugin_id=plugin_id,
            config=config,
            enabled=enabled,
            interval_minutes=interval,
            updated_at=_now(),
        )

    def with_fetch_result(
        self,
        *,
        status: str,
        error: str = "",
        fetched_at: datetime | None = None,
        touch_fetched_at: bool = True,
    ) -> Source:
        if status not in SOURCE_STATUSES:
            raise ValueError("invalid source status")
        next_fetched = self.last_fetched_at
        if touch_fetched_at:
            next_fetched = fetched_at if fetched_at is not None else _now()
        return replace(
            self,
            last_status=status,
            last_error=(error or "")[:2000],
            last_fetched_at=next_fetched,
            updated_at=_now(),
        )

    def is_due(self, now: datetime | None = None) -> bool:
        if not self.enabled:
            return False
        if self.last_status == "running":
            return False
        clock = now or _now()
        if self.last_fetched_at is None:
            return True
        elapsed = (clock - self.last_fetched_at).total_seconds()
        return elapsed >= self.interval_minutes * 60


@dataclass
class Article:
    id: str
    source_id: str
    external_id: str
    title: str
    content: str
    content_format: str
    published_at: datetime | None
    author: str
    cover_url: str | None
    url: str | None
    fetched_at: datetime

    @classmethod
    def from_parsed(cls, source_id: str, raw: dict[str, Any]) -> Article:
        external_id = str(raw.get("external_id") or "").strip()
        if not external_id or len(external_id) > MAX_EXTERNAL_ID_LENGTH:
            raise ValueError("文章 external_id 无效")
        title = str(raw.get("title") or "").strip() or "(无标题)"
        if len(title) > MAX_TITLE_LENGTH:
            title = title[:MAX_TITLE_LENGTH]
        content = str(raw.get("content") or "")
        if len(content) > MAX_CONTENT_CHARS:
            content = content[:MAX_CONTENT_CHARS]
        content_format = str(raw.get("content_format") or "html").strip().lower()
        if content_format not in CONTENT_FORMATS:
            raise ValueError("content_format 须为 markdown 或 html")
        author = str(raw.get("author") or "").strip()
        if len(author) > MAX_AUTHOR_LENGTH:
            author = author[:MAX_AUTHOR_LENGTH]
        return cls(
            str(uuid4()),
            source_id,
            external_id,
            title,
            content,
            content_format,
            _parse_datetime(raw.get("published_at")),
            author,
            _optional_http_url(raw.get("cover_url"), field_name="cover_url"),
            _optional_http_url(raw.get("url"), field_name="url"),
            _now(),
        )

    def merge_from(self, other: Article) -> Article:
        return replace(
            self,
            title=other.title,
            content=other.content,
            content_format=other.content_format,
            published_at=other.published_at,
            author=other.author,
            cover_url=other.cover_url,
            url=other.url,
            fetched_at=other.fetched_at,
        )


class PluginRepository(Protocol):
    async def save(self, plugin: Plugin) -> None: ...
    async def by_id(self, plugin_id: str) -> Plugin | None: ...
    async def list(self) -> list[Plugin]: ...
    async def delete(self, plugin_id: str) -> bool: ...
    async def ensure_indexes(self) -> None: ...


class SourceRepository(Protocol):
    async def save(self, source: Source) -> None: ...
    async def by_id(self, source_id: str) -> Source | None: ...
    async def list(self) -> list[Source]: ...
    async def delete(self, source_id: str) -> bool: ...
    async def ensure_indexes(self) -> None: ...


class ArticleRepository(Protocol):
    async def upsert(self, article: Article) -> Article: ...
    async def by_id(self, article_id: str) -> Article | None: ...
    async def list(
        self,
        *,
        source_id: str | None = None,
        query: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> list[Article]: ...
    async def delete_by_source(self, source_id: str) -> int: ...
    async def ensure_indexes(self) -> None: ...


class SubscriptionDomainService:
    def __init__(
        self,
        plugins: PluginRepository,
        sources: SourceRepository,
        articles: ArticleRepository,
    ):
        self.plugins = plugins
        self.sources = sources
        self.articles = articles

    async def initialize(self) -> None:
        await self.plugins.ensure_indexes()
        await self.sources.ensure_indexes()
        await self.articles.ensure_indexes()

    async def list_plugins(self) -> list[Plugin]:
        return await self.plugins.list()

    async def get_plugin(self, plugin_id: str) -> Plugin:
        plugin = await self.plugins.by_id(plugin_id)
        if plugin is None:
            raise LookupError("插件不存在")
        return plugin

    async def create_plugin(self, changes: dict[str, Any]) -> Plugin:
        plugin = Plugin.create(
            str(changes.get("name") or ""),
            str(changes.get("script") or ""),
            description=str(changes.get("description") or ""),
            builtin=bool(changes.get("builtin") or False),
            ident=changes.get("id"),
        )
        await self.plugins.save(plugin)
        return plugin

    async def update_plugin(self, plugin_id: str, changes: dict[str, Any]) -> Plugin:
        plugin = (await self.get_plugin(plugin_id)).apply(changes)
        await self.plugins.save(plugin)
        return plugin

    async def delete_plugin(self, plugin_id: str) -> None:
        plugin = await self.get_plugin(plugin_id)
        if plugin.builtin:
            raise ValueError("内置插件不可删除")
        linked = [item for item in await self.sources.list() if item.plugin_id == plugin_id]
        if linked:
            raise ValueError("仍有订阅源使用该插件，请先更换或删除订阅源")
        if not await self.plugins.delete(plugin_id):
            raise LookupError("插件不存在")

    async def list_sources(self) -> list[Source]:
        return await self.sources.list()

    async def get_source(self, source_id: str) -> Source:
        source = await self.sources.by_id(source_id)
        if source is None:
            raise LookupError("订阅源不存在")
        return source

    async def create_source(self, changes: dict[str, Any]) -> Source:
        await self.get_plugin(str(changes.get("plugin_id") or ""))
        source = Source.create(changes)
        await self.sources.save(source)
        return source

    async def update_source(self, source_id: str, changes: dict[str, Any]) -> Source:
        if "plugin_id" in changes:
            await self.get_plugin(str(changes.get("plugin_id") or ""))
        source = (await self.get_source(source_id)).apply(changes)
        await self.sources.save(source)
        return source

    async def delete_source(self, source_id: str) -> None:
        await self.get_source(source_id)
        await self.articles.delete_by_source(source_id)
        if not await self.sources.delete(source_id):
            raise LookupError("订阅源不存在")

    async def mark_source_running(self, source_id: str) -> Source:
        source = (await self.get_source(source_id)).with_fetch_result(
            status="running", error="", touch_fetched_at=False
        )
        await self.sources.save(source)
        return source

    async def mark_source_result(
        self, source_id: str, *, status: str, error: str = ""
    ) -> Source:
        source = (await self.get_source(source_id)).with_fetch_result(status=status, error=error)
        await self.sources.save(source)
        return source

    async def upsert_articles(
        self, source_id: str, parsed: list[dict[str, Any]]
    ) -> list[Article]:
        await self.get_source(source_id)
        saved: list[Article] = []
        for raw in parsed:
            article = Article.from_parsed(source_id, raw)
            saved.append(await self.articles.upsert(article))
        return saved

    async def list_articles(
        self,
        *,
        source_id: str | None = None,
        query: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> list[Article]:
        return await self.articles.list(
            source_id=source_id, query=query, offset=offset, limit=limit
        )

    async def get_article(self, article_id: str) -> Article:
        article = await self.articles.by_id(article_id)
        if article is None:
            raise LookupError("文章不存在")
        return article

    def validate_create_source(self, changes: dict[str, Any]) -> None:
        Source.create(changes)

    def validate_update_source(self, changes: dict[str, Any]) -> None:
        Source(
            "00000000-0000-0000-0000-000000000000",
            "x",
            "https://example.com",
            "plugin",
            {},
            True,
            60,
            None,
            "idle",
            "",
            _now(),
            _now(),
        ).apply(changes)
