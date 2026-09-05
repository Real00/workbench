from dataclasses import replace
from typing import Any
from uuid import uuid4

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from pymongo import AsyncMongoClient

from api.http import auth_middleware, error_middleware
from capture.domain import Capture
from capture.module import CaptureModule
from shared.config import Settings
from shared.module import ModuleContext
from shared.security import SecurityService
from shared.web_keys import SECURITY


class MemoryCaptures:
    def __init__(self):
        self.items: dict[tuple[str, str], Capture] = {}

    async def create(self, item: Capture) -> Capture:
        key = (item.owner_id, item.id)
        if key in self.items and self.items[key].content != item.content:
            raise ValueError("conflicting retry")
        self.items.setdefault(key, item)
        return self.items[key]

    async def list(self, owner: str, query: str, archived: bool, offset: int) -> list[Capture]:
        items = [item for item in self.items.values() if item.owner_id == owner
                 and item.archived == archived and query.lower() in item.content.lower()]
        return sorted(items, key=lambda item: (item.pinned, item.created_at), reverse=True)[
            offset:offset + 50
        ]

    async def update(self, owner: str, ident: str, changes: dict[str, bool]) -> Capture:
        key = (owner, ident)
        if key not in self.items:
            raise LookupError("not found")
        self.items[key] = replace(self.items[key], **changes)
        return self.items[key]


async def test_capture_http_lifecycle_and_owner_isolation() -> None:
    security = SecurityService("test-secret-with-at-least-32-characters", 60)
    mongo: AsyncMongoClient[Any] = AsyncMongoClient()
    app = web.Application(middlewares=[error_middleware, auth_middleware])
    app[SECURITY] = security
    CaptureModule().register(app, ModuleContext(
        Settings(), mongo, security, {"capture_repository": MemoryCaptures()}
    ))
    client = TestClient(TestServer(app))
    await client.start_server()
    alice = {"Authorization": f"Bearer {security.issue_access_token('alice', 'member')}"}
    bob = {"Authorization": f"Bearer {security.issue_access_token('bob', 'member')}"}
    path = "/api/v1/captures"
    ident = str(uuid4())
    try:
        assert (await client.get(path)).status == 401
        assert (await client.post(path, headers=alice, json={
            "id": ident, "content": "   "
        })).status == 400
        payload = {"id": ident, "content": "  发布日志自动整理  "}
        created = await client.post(path, headers=alice, json=payload)
        assert created.status == 201
        assert (await created.json())["content"] == "发布日志自动整理"
        await client.post(path, headers=alice, json=payload)
        assert len(await (await client.get(path, headers=alice)).json()) == 1
        assert await (await client.get(path, headers=bob)).json() == []
        assert (await client.patch(f"{path}/{ident}", headers=bob,
                                   json={"archived": True})).status == 404
        assert await (await client.get(f"{path}?q=不存在", headers=alice)).json() == []
        assert len(await (await client.get(f"{path}?q=发布", headers=alice)).json()) == 1
        assert (await client.patch(f"{path}/{ident}", headers=alice,
                                   json={"owner_id": "bob"})).status == 422
        assert (await client.patch(f"{path}/{ident}", headers=alice,
                                   json={"pinned": None})).status == 422
        pinned = await client.patch(f"{path}/{ident}", headers=alice, json={"pinned": True})
        assert (await pinned.json())["pinned"] is True
        await client.patch(f"{path}/{ident}", headers=alice, json={"archived": True})
        assert await (await client.get(path, headers=alice)).json() == []
        assert len(await (await client.get(f"{path}?archived=true", headers=alice)).json()) == 1
        await client.patch(f"{path}/{ident}", headers=alice, json={"archived": False})
        assert len(await (await client.get(path, headers=alice)).json()) == 1
    finally:
        await client.close()
        await mongo.close()


def test_pulse_accepts_full_capture_with_analysis_prompt() -> None:
    from pulse.routes import AIPreviewInput

    original = "灵" * 20000
    payload = AIPreviewInput(instruction=f"请分析这条记录：\n{original}")
    assert payload.instruction.endswith(original)
