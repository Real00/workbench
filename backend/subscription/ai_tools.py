from __future__ import annotations

from typing import Any

from pydantic_ai import ModelRetry, RunContext

from pulse.deps import AgentDeps
from shared.ai import ModuleAiContribution

INSTRUCTIONS = (
    "Subscription module: remote feeds parsed by Python plugins. "
    "Platform fetches the source URL; plugins only parse body into articles. "
    "Article fields: external_id, title, content, content_format (markdown|html), "
    "published_at, author, cover_url, url. "
    "Use list_subscription_sources / list_subscription_articles to inspect data. "
    "Queue create_subscription_source or update_subscription_source for writes; "
    "never claim a source was saved until the user confirms. "
    "Do not delete sources or plugins via tools. "
    "Plugin scripts must subclass SubscriptionParser; see docs/subscription-plugin-spec.md."
)


def _subscription(ctx: RunContext[AgentDeps]):
    if ctx.deps.subscription is None:
        raise ModelRetry("subscription module is not available")
    return ctx.deps.subscription


def _changes(**fields: Any) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if value is not None}


async def list_subscription_sources(ctx: RunContext[AgentDeps]) -> list[dict[str, Any]]:
    domain = _subscription(ctx)
    sources = await domain.list_sources()
    return [
        {
            "id": item.id,
            "name": item.name,
            "url": item.url,
            "plugin_id": item.plugin_id,
            "enabled": item.enabled,
            "interval_minutes": item.interval_minutes,
            "last_status": item.last_status,
            "last_error": item.last_error,
            "last_fetched_at": None
            if item.last_fetched_at is None
            else item.last_fetched_at.isoformat(),
        }
        for item in sources
    ]


async def list_subscription_plugins(ctx: RunContext[AgentDeps]) -> list[dict[str, Any]]:
    domain = _subscription(ctx)
    plugins = await domain.list_plugins()
    return [
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "builtin": item.builtin,
        }
        for item in plugins
    ]


async def list_subscription_articles(
    ctx: RunContext[AgentDeps],
    source_id: str | None = None,
    query: str = "",
    limit: int = 20,
) -> list[dict[str, Any]]:
    domain = _subscription(ctx)
    articles = await domain.list_articles(
        source_id=source_id, query=query, offset=0, limit=min(max(limit, 1), 50)
    )
    return [
        {
            "id": item.id,
            "source_id": item.source_id,
            "external_id": item.external_id,
            "title": item.title,
            "author": item.author,
            "content_format": item.content_format,
            "published_at": None if item.published_at is None else item.published_at.isoformat(),
            "url": item.url,
            "cover_url": item.cover_url,
        }
        for item in articles
    ]


async def read_subscription_article(
    ctx: RunContext[AgentDeps], article_id: str
) -> dict[str, Any]:
    domain = _subscription(ctx)
    try:
        item = await domain.get_article(article_id)
    except LookupError as exc:
        raise ModelRetry(f"article not found: {article_id}") from exc
    return {
        "id": item.id,
        "source_id": item.source_id,
        "external_id": item.external_id,
        "title": item.title,
        "content": item.content,
        "content_format": item.content_format,
        "author": item.author,
        "published_at": None if item.published_at is None else item.published_at.isoformat(),
        "url": item.url,
        "cover_url": item.cover_url,
    }


async def create_subscription_source(
    ctx: RunContext[AgentDeps],
    name: str,
    url: str,
    plugin_id: str,
    interval_minutes: int = 60,
    enabled: bool = True,
) -> dict[str, str]:
    domain = _subscription(ctx)
    changes = _changes(
        name=name,
        url=url,
        plugin_id=plugin_id,
        interval_minutes=interval_minutes,
        enabled=enabled,
    )
    try:
        domain.validate_create_source(changes)
        await domain.get_plugin(plugin_id)
    except (ValueError, LookupError) as exc:
        raise ModelRetry(str(exc)) from exc
    ctx.deps.pending.append({"op": "create_source", "changes": changes})
    return {"status": "queued", "op": "create_source"}


async def update_subscription_source(
    ctx: RunContext[AgentDeps],
    source_id: str,
    name: str | None = None,
    url: str | None = None,
    plugin_id: str | None = None,
    interval_minutes: int | None = None,
    enabled: bool | None = None,
) -> dict[str, str]:
    domain = _subscription(ctx)
    try:
        await domain.get_source(source_id)
    except LookupError as exc:
        raise ModelRetry(f"source not found: {source_id}") from exc
    changes = _changes(
        name=name,
        url=url,
        plugin_id=plugin_id,
        interval_minutes=interval_minutes,
        enabled=enabled,
    )
    if not changes:
        raise ModelRetry("provide at least one field to update")
    try:
        domain.validate_update_source(changes)
        if plugin_id:
            await domain.get_plugin(plugin_id)
    except (ValueError, LookupError) as exc:
        raise ModelRetry(str(exc)) from exc
    ctx.deps.pending.append(
        {"op": "update_source", "source_id": source_id, "changes": changes}
    )
    return {"status": "queued", "op": "update_source"}


def subscription_ai_contribution() -> ModuleAiContribution:
    return ModuleAiContribution(
        id="subscription",
        instructions=INSTRUCTIONS,
        tools=(
            list_subscription_sources,
            list_subscription_plugins,
            list_subscription_articles,
            read_subscription_article,
            create_subscription_source,
            update_subscription_source,
        ),
    )
