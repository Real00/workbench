"""订阅模块测试：领域规则、插件子进程、刷新与 API。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from aiohttp.test_utils import TestClient, TestServer

from app import create_app
from shared.config import Settings
from subscription.domain import (
    Article,
    Plugin,
    Source,
    SubscriptionDomainService,
    validate_plugin_script,
)
from subscription.fetcher import FetchResult
from subscription.plugin_runner import PluginSubprocessRunner
from tests.fakes import (
    MemoryAISettingsRepository,
    MemoryArticleRepository,
    MemoryDeviceRepository,
    MemoryMemberRepository,
    MemoryPluginRepository,
    MemoryProjectRepository,
    MemoryResourceStorage,
    MemorySkillsRepository,
    MemorySourceRepository,
    MemoryTaskRepository,
    MemoryUserRepository,
    knowledge_overrides,
)

MINIMAL_SCRIPT = """
from subscription.plugin_runtime.base import ParsePayload, ParsedArticle, SubscriptionParser

class DemoParser(SubscriptionParser):
    def parse(self, payload: ParsePayload) -> list[ParsedArticle]:
        return [
            ParsedArticle(
                external_id="a1",
                title="Hello",
                content="# hi",
                content_format="markdown",
                author="Ada",
                url="https://example.com/a1",
            )
        ]
"""


class FakeFetcher:
    def __init__(self, body: str = "<rss></rss>", url: str = "https://example.com/feed"):
        self.body = body
        self.url = url
        self.calls: list[str] = []

    async def fetch(self, url: str, *, headers: dict[str, str] | None = None) -> FetchResult:
        self.calls.append(url)
        return FetchResult(url=self.url, body=self.body, status=200, content_type="application/xml")


def test_validate_plugin_script_requires_parser_subclass() -> None:
    with pytest.raises(ValueError, match="SubscriptionParser"):
        validate_plugin_script("x = 1\n")
    validate_plugin_script(MINIMAL_SCRIPT)


def test_source_is_due() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    source = Source.create(
        {
            "name": "feed",
            "url": "https://example.com/feed",
            "plugin_id": "p1",
            "interval_minutes": 60,
        }
    )
    assert source.is_due(now)
    source = source.with_fetch_result(status="ok", fetched_at=now)
    assert not source.is_due(now + timedelta(minutes=30))
    assert source.is_due(now + timedelta(minutes=61))
    disabled = source.apply({"enabled": False})
    assert not disabled.is_due(now + timedelta(hours=10))


def test_article_from_parsed_rejects_bad_format() -> None:
    with pytest.raises(ValueError, match="content_format"):
        Article.from_parsed("s1", {"external_id": "1", "title": "t", "content_format": "pdf"})


@pytest.mark.asyncio
async def test_plugin_runner_parses_minimal_script() -> None:
    runner = PluginSubprocessRunner(timeout_seconds=15)
    result = await runner.run(
        MINIMAL_SCRIPT,
        url="https://example.com/feed",
        body="ignored",
        config={},
    )
    assert len(result.articles) == 1
    assert result.articles[0]["external_id"] == "a1"
    assert result.articles[0]["content_format"] == "markdown"


@pytest.mark.asyncio
async def test_plugin_runner_rejects_bad_json_exit() -> None:
    runner = PluginSubprocessRunner(timeout_seconds=10)
    bad = """
from subscription.plugin_runtime.base import ParsePayload, ParsedArticle, SubscriptionParser
class Boom(SubscriptionParser):
    def parse(self, payload: ParsePayload):
        raise RuntimeError("boom")
"""
    with pytest.raises(ValueError, match="插件执行失败"):
        await runner.run(bad, url="https://example.com", body="", config={})


@pytest.mark.asyncio
async def test_domain_upsert_articles_idempotent() -> None:
    domain = SubscriptionDomainService(
        MemoryPluginRepository(),
        MemorySourceRepository(),
        MemoryArticleRepository(),
    )
    plugin = await domain.create_plugin(
        {"name": "demo", "script": MINIMAL_SCRIPT, "description": ""}
    )
    source = await domain.create_source(
        {
            "name": "s",
            "url": "https://example.com/feed",
            "plugin_id": plugin.id,
        }
    )
    first = await domain.upsert_articles(
        source.id,
        [{"external_id": "x", "title": "One", "content": "a", "content_format": "html"}],
    )
    second = await domain.upsert_articles(
        source.id,
        [{"external_id": "x", "title": "Two", "content": "b", "content_format": "html"}],
    )
    assert first[0].id == second[0].id
    assert second[0].title == "Two"
    listed = await domain.list_articles(source_id=source.id)
    assert len(listed) == 1


async def _client(**extra) -> TestClient:
    overrides = knowledge_overrides()
    overrides.update(extra)
    app = create_app(
        Settings(admin_password="password123"),
        user_repository=MemoryUserRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        device_repository=MemoryDeviceRepository(),
        ai_repository=MemoryAISettingsRepository(),
        ai_skills_repository=MemorySkillsRepository(),
        resource_storage=MemoryResourceStorage(),
        **overrides,
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    return client


async def _auth(client: TestClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "password123"}
    )
    assert response.status == 200
    return {"Authorization": f"Bearer {(await response.json())['access_token']}"}


@pytest.mark.asyncio
async def test_subscription_api_refresh_flow() -> None:
    fetcher = FakeFetcher(
        body="""<?xml version="1.0"?>
        <rss version="2.0"><channel>
          <item>
            <title>T1</title>
            <guid>g1</guid>
            <link>https://example.com/1</link>
            <description>Hello</description>
          </item>
        </channel></rss>"""
    )
    client = await _client(subscription_fetcher=fetcher)
    try:
        headers = await _auth(client)
        plugins = await (await client.get("/api/v1/subscription/plugins", headers=headers)).json()
        assert any(item["id"] == "builtin-rss-atom" for item in plugins)
        builtin = next(item for item in plugins if item["id"] == "builtin-rss-atom")
        created = await client.post(
            "/api/v1/subscription/sources",
            headers=headers,
            json={
                "name": "Demo",
                "url": "https://example.com/feed",
                "plugin_id": builtin["id"],
                "interval_minutes": 30,
            },
        )
        assert created.status == 200
        source = await created.json()
        refreshed = await client.post(
            f"/api/v1/subscription/sources/{source['id']}/refresh",
            headers=headers,
        )
        assert refreshed.status == 200
        body = await refreshed.json()
        assert body["upserted"] == 1
        assert fetcher.calls == ["https://example.com/feed"]
        articles = await (
            await client.get("/api/v1/subscription/articles", headers=headers)
        ).json()
        assert len(articles) == 1
        assert articles[0]["title"] == "T1"
        assert articles[0]["content_format"] == "html"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_builtin_plugin_script_immutable() -> None:
    client = await _client()
    try:
        headers = await _auth(client)
        response = await client.patch(
            "/api/v1/subscription/plugins/builtin-rss-atom",
            headers=headers,
            json={"script": MINIMAL_SCRIPT},
        )
        assert response.status == 400
    finally:
        await client.close()


def test_plugin_create_builtin_allowed() -> None:
    plugin = Plugin.create(
        "RSS",
        MINIMAL_SCRIPT,
        description="d",
        builtin=True,
        ident="builtin-x",
    )
    assert plugin.builtin
    assert plugin.id == "builtin-x"
    with pytest.raises(ValueError, match="内置插件"):
        plugin.apply({"script": MINIMAL_SCRIPT})
