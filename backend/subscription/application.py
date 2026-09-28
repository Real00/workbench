from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from shared.events import ChangeEventBus
from subscription.builtin_rss import (
    BUILTIN_RSS_PLUGIN_DESCRIPTION,
    BUILTIN_RSS_PLUGIN_ID,
    BUILTIN_RSS_PLUGIN_NAME,
    BUILTIN_RSS_SCRIPT,
)
from subscription.domain import SubscriptionDomainService
from subscription.fetcher import HttpFetcher
from subscription.plugin_runner import PluginSubprocessRunner


class EventPublisher(Protocol):
    def publish(self, scope: str, action: str) -> None: ...


class SubscriptionApplicationService:
    def __init__(
        self,
        domain: SubscriptionDomainService,
        *,
        fetcher: HttpFetcher | None = None,
        runner: PluginSubprocessRunner | None = None,
        event_bus: ChangeEventBus | EventPublisher | None = None,
        enable_scheduler: bool = True,
    ):
        self.domain = domain
        self.fetcher = fetcher or HttpFetcher()
        self.runner = runner or PluginSubprocessRunner()
        self.event_bus = event_bus
        self.enable_scheduler = enable_scheduler
        self.scheduler: Any = None
        self._refresh_locks: set[str] = set()

    async def initialize(self) -> None:
        await self.domain.initialize()
        existing = await self.domain.plugins.by_id(BUILTIN_RSS_PLUGIN_ID)
        if existing is None:
            await self.domain.create_plugin(
                {
                    "id": BUILTIN_RSS_PLUGIN_ID,
                    "name": BUILTIN_RSS_PLUGIN_NAME,
                    "description": BUILTIN_RSS_PLUGIN_DESCRIPTION,
                    "script": BUILTIN_RSS_SCRIPT,
                    "builtin": True,
                }
            )

    # —— plugins ——
    async def list_plugins(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in await self.domain.list_plugins()]

    async def get_plugin(self, plugin_id: str) -> dict[str, Any]:
        return asdict(await self.domain.get_plugin(plugin_id))

    async def create_plugin(self, changes: dict[str, Any]) -> dict[str, Any]:
        return asdict(await self.domain.create_plugin(changes))

    async def update_plugin(self, plugin_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        return asdict(await self.domain.update_plugin(plugin_id, changes))

    async def delete_plugin(self, plugin_id: str) -> None:
        await self.domain.delete_plugin(plugin_id)

    async def trial_plugin(
        self,
        plugin_id: str,
        *,
        body: str,
        url: str = "https://example.com/feed",
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plugin = await self.domain.get_plugin(plugin_id)
        result = await self.runner.run(
            plugin.script, url=url, body=body, config=config or {}
        )
        articles = []
        for raw in result.articles:
            # 校验字段但不入库
            from subscription.domain import Article

            articles.append(asdict(Article.from_parsed("trial", raw)))
        return {"articles": articles, "count": len(articles)}

    # —— sources ——
    async def list_sources(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in await self.domain.list_sources()]

    async def get_source(self, source_id: str) -> dict[str, Any]:
        return asdict(await self.domain.get_source(source_id))

    async def create_source(self, changes: dict[str, Any]) -> dict[str, Any]:
        return asdict(await self.domain.create_source(changes))

    async def update_source(self, source_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        return asdict(await self.domain.update_source(source_id, changes))

    async def delete_source(self, source_id: str) -> None:
        await self.domain.delete_source(source_id)

    # —— articles ——
    async def list_articles(
        self,
        *,
        source_id: str | None = None,
        query: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return [
            asdict(item)
            for item in await self.domain.list_articles(
                source_id=source_id, query=query, offset=offset, limit=limit
            )
        ]

    async def get_article(self, article_id: str) -> dict[str, Any]:
        return asdict(await self.domain.get_article(article_id))

    async def refresh_source(self, source_id: str) -> dict[str, Any]:
        if source_id in self._refresh_locks:
            raise ValueError("该订阅源正在刷新")
        self._refresh_locks.add(source_id)
        try:
            source = await self.domain.mark_source_running(source_id)
            plugin = await self.domain.get_plugin(source.plugin_id)
            try:
                headers = {}
                raw_headers = source.config.get("headers")
                if isinstance(raw_headers, dict):
                    headers = {str(k): str(v) for k, v in raw_headers.items()}
                fetched = await self.fetcher.fetch(source.url, headers=headers or None)
                parsed = await self.runner.run(
                    plugin.script,
                    url=fetched.url,
                    body=fetched.body,
                    config=source.config,
                )
                articles = await self.domain.upsert_articles(source_id, parsed.articles)
                await self.domain.mark_source_result(source_id, status="ok", error="")
                if self.event_bus is not None:
                    self.event_bus.publish("subscription", "updated")
                return {
                    "source_id": source_id,
                    "upserted": len(articles),
                    "status": "ok",
                }
            except Exception as exc:  # noqa: BLE001 — 刷新失败记入源状态
                await self.domain.mark_source_result(source_id, status="error", error=str(exc))
                if self.event_bus is not None:
                    self.event_bus.publish("subscription", "updated")
                raise
        finally:
            self._refresh_locks.discard(source_id)

    async def refresh_due_sources(self, *, limit: int = 2) -> list[dict[str, Any]]:
        due = [item for item in await self.domain.list_sources() if item.is_due()]
        results: list[dict[str, Any]] = []
        for source in due[:limit]:
            try:
                results.append(await self.refresh_source(source.id))
            except Exception as exc:  # noqa: BLE001 — 调度继续下一个
                results.append(
                    {"source_id": source.id, "status": "error", "error": str(exc)}
                )
        return results

    async def apply_operation(self, operation: dict[str, Any]) -> dict[str, Any]:
        op = operation.get("op")
        if op == "create_source":
            return await self.create_source(operation.get("changes") or {})
        if op == "update_source":
            return await self.update_source(
                str(operation.get("source_id") or ""), operation.get("changes") or {}
            )
        raise ValueError(f"unknown subscription operation: {op}")
