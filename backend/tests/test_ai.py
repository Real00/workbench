import json
from collections.abc import AsyncIterator
from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from pydantic_ai import CancellationToken, ModelRetry
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from ai_settings.application import AISettingsApplicationService
from ai_settings.domain import AISettingsDomainService
from progress.ai_application import AITaskApplicationService
from progress.ai_tools import (
    AgentDeps,
    add_progress_entry,
    create_project,
    create_task,
    list_members,
    record_member_evaluation,
    update_member,
    update_project,
    update_task,
)
from progress.domain import ProgressDomainService
from shared.ai import clock_block
from shared.security import SecurityService
from tests.fakes import (
    MemoryAISettingsRepository,
    MemoryMemberRepository,
    MemoryProjectRepository,
    MemoryResourceStorage,
    MemoryTaskRepository,
    MemoryUserRepository,
    knowledge_overrides,
)


class FakeProgressAgent:
    def __init__(
        self,
        events: list[dict[str, object]],
        pending: list[dict[str, object]] | None = None,
    ):
        self.events = events
        self.pending = pending or []
        self.prompts: list[str] = []
        self.histories: list[list[object]] = []

    async def stream(
        self,
        prompt: str,
        deps: AgentDeps,
        settings: object,
        cancellation_token: object | None = None,
        message_history: list[object] | None = None,
    ) -> AsyncIterator[dict[str, object]]:
        assert settings
        self.prompts.append(prompt)
        self.histories.append(list(message_history or []))
        deps.pending.extend(self.pending)
        deps.produced_messages[:] = [
            *(message_history or []),
            ModelRequest(parts=[UserPromptPart(content=prompt)]),
            ModelResponse(parts=[TextPart(content=f"reply-{len(self.prompts)}")]),
        ]
        for event in self.events:
            if cancellation_token is not None and getattr(
                cancellation_token, "cancelled", False
            ):
                return
            yield event


async def build_service(
    events: list[dict[str, object]] | None = None,
    pending: list[dict[str, object]] | None = None,
) -> tuple[AITaskApplicationService, ProgressDomainService, FakeProgressAgent, str]:
    security = SecurityService("test-secret-with-at-least-32-characters", 60)
    ai_repository = MemoryAISettingsRepository()
    ai_domain = AISettingsDomainService(ai_repository)
    await ai_domain.configure(
        "https://example.test/v1", "test-model", security.encrypt("secret-api-key")
    )
    progress = ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository())
    member = await progress.create_member({"name": "Alice", "title": "Designer"})
    settings_reader = AISettingsApplicationService(ai_domain, security)
    agent = FakeProgressAgent(events or [{"type": "text", "delta": "将创建设计任务。"}], pending)
    service = AITaskApplicationService(
        settings_reader, progress, security, 60, agent=agent
    )
    return service, progress, agent, member.id


def test_map_agent_event_streams_thinking_deltas() -> None:
    from pydantic_ai.messages import (
        PartDeltaEvent,
        PartStartEvent,
        ThinkingPart,
        ThinkingPartDelta,
    )

    from progress.agent import map_agent_event

    start = map_agent_event(PartStartEvent(index=0, part=ThinkingPart(content="先核对成员")))
    assert start == {"type": "thinking", "delta": "先核对成员"}
    delta = map_agent_event(
        PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta="再排队更新"))
    )
    assert delta == {"type": "thinking", "delta": "再排队更新"}


async def test_create_task_tool_queues_without_writing() -> None:
    progress = ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository())
    member = await progress.create_member({"name": "Alice", "title": "Designer"})
    ctx = SimpleNamespace(deps=AgentDeps(progress=progress))
    result = await create_task(ctx, title="Design UI", assignee_name="Alice", progress=20)
    assert result["queued"] is True
    assert ctx.deps.pending[0]["changes"]["assignee_id"] == member.id
    assert await progress.list_tasks({}) == []


async def test_list_members_tool_exposes_skills_and_open_load() -> None:
    progress = ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository())
    member = await progress.create_member(
        {
            "name": "Alice",
            "title": "Designer",
            "skills": ["UI", "工单对接"],
            "background": "做过 MYAI 工单联调",
        }
    )
    await progress.create(
        {"title": "登录页", "status": "in_progress", "assignee_id": member.id},
        "admin",
    )
    ctx = SimpleNamespace(deps=AgentDeps(progress=progress))
    listed = await list_members(ctx)
    assert listed == [
        {
            "id": member.id,
            "name": "Alice",
            "title": "Designer",
            "skills": ["UI", "工单对接"],
            "background": "做过 MYAI 工单联调",
            "open_tasks": 1,
            "operator": False,
        }
    ]


async def test_update_member_tool_queues_profile_then_confirm_writes() -> None:
    service, progress, agent, _ = await build_service()
    member = await progress.create_member({"name": "张三", "title": "工程师"})
    ctx = SimpleNamespace(deps=AgentDeps(progress=progress))
    queued = await update_member(
        ctx,
        name="张三",
        add_skills=["DevOps", "后端业务"],
        background="负责 myai 相关系统开发",
    )
    assert queued["queued"] is True
    assert (await progress.get_member(member.id)).skills == []
    agent.pending = ctx.deps.pending
    events = [event async for event in service.stream("记录张三的技能和背景")]
    confirmed = await service.confirm(events[-1]["confirmation_token"], "admin")
    assert confirmed[0]["skills"] == ["DevOps", "后端业务"]
    assert confirmed[0]["background"] == "负责 myai 相关系统开发"


async def test_record_member_evaluation_tool_queues_then_confirm_writes() -> None:
    service, progress, agent, _ = await build_service()
    member = await progress.create_member({"name": "张三", "title": "工程师"})
    ctx = SimpleNamespace(deps=AgentDeps(progress=progress))
    queued = await record_member_evaluation(
        ctx, kind="highlight", content="联调推进很稳", name="张三"
    )
    assert queued["queued"] is True
    assert (await progress.get_member(member.id)).evaluations == []
    agent.pending = ctx.deps.pending
    events = [event async for event in service.stream("记一下张三这次表现不错")]
    confirmed = await service.confirm(events[-1]["confirmation_token"], "admin")
    assert confirmed[0]["evaluations"][0]["kind"] == "highlight"
    assert confirmed[0]["evaluations"][0]["content"] == "联调推进很稳"


async def test_record_member_evaluation_requires_member_and_content() -> None:
    progress = ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository())
    ctx = SimpleNamespace(deps=AgentDeps(progress=progress))
    with pytest.raises(ModelRetry, match="provide member name"):
        await record_member_evaluation(ctx, kind="note", content="评价")
    with pytest.raises(ModelRetry, match="unknown team member"):
        await record_member_evaluation(ctx, kind="note", content="评价", name="张三")
    await progress.create_member({"name": "张三"})
    with pytest.raises(ModelRetry, match="content"):
        await record_member_evaluation(ctx, kind="note", content="   ", name="张三")


async def test_create_project_tool_queues_then_confirm_writes() -> None:
    service, progress, agent, member_id = await build_service()
    ctx = SimpleNamespace(deps=AgentDeps(progress=progress))
    queued = await create_project(
        ctx,
        name="MYAI 工单平台",
        description="工单系统二期",
        started_at=date(2026, 9, 1),
        status="active",
        member_names=["Alice"],
    )
    assert queued["queued"] is True
    assert ctx.deps.pending[0]["changes"]["member_ids"] == [member_id]
    assert await progress.list_projects() == []
    agent.pending = ctx.deps.pending
    events = [event async for event in service.stream("建一个 MYAI 工单平台项目")]
    confirmed = await service.confirm(events[-1]["confirmation_token"], "admin")
    assert confirmed[0]["name"] == "MYAI 工单平台"
    assert confirmed[0]["status"] == "active"
    assert confirmed[0]["started_at"] == date(2026, 9, 1)
    assert confirmed[0]["member_ids"] == [member_id]

    with pytest.raises(ModelRetry, match="already exists"):
        await create_project(ctx, name="myai 工单平台")


async def test_update_project_tool_queues_status_and_members() -> None:
    service, progress, agent, member_id = await build_service()
    project = await progress.create_project(
        {"name": "MYAI 工单平台", "member_ids": [member_id]}
    )
    other = await progress.create_member({"name": "Bob", "title": "Tester"})
    ctx = SimpleNamespace(deps=AgentDeps(progress=progress))
    queued = await update_project(
        ctx,
        name="MYAI 工单平台",
        status="completed",
        add_members=["Bob"],
        remove_members=["Alice"],
    )
    assert queued["queued"] is True
    assert ctx.deps.pending[0]["changes"]["member_ids"] == [other.id]
    agent.pending = ctx.deps.pending
    events = [event async for event in service.stream("项目做完了，把状态改一下")]
    confirmed = await service.confirm(events[-1]["confirmation_token"], "admin")
    assert confirmed[0]["status"] == "completed"
    assert confirmed[0]["member_ids"] == [other.id]
    assert project.id


async def test_update_project_tool_rejects_unknown_project() -> None:
    progress = ProgressDomainService(
        MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository()
    )
    ctx = SimpleNamespace(deps=AgentDeps(progress=progress))
    with pytest.raises(ModelRetry, match="provide project name"):
        await update_project(ctx, status="active")
    with pytest.raises(ModelRetry, match="unknown project"):
        await update_project(ctx, name="不存在", status="active")


async def test_stream_maintains_multi_turn_session_history() -> None:
    service, _, agent, _ = await build_service()
    first_events = [event async for event in service.stream("查看任务")]
    done = first_events[-1]
    assert done["type"] == "done"
    session_id = done["session_id"]
    assert session_id
    assert agent.histories[0] == []

    second_events = [event async for event in service.stream("继续", session_id=session_id)]
    assert second_events[-1]["session_id"] == session_id
    assert len(agent.histories[1]) == 2
    assert [event async for event in service.stream("换个话题")] [-1]["session_id"] != session_id

    assert all("session_id" not in event or event["session_id"] for event in first_events)


async def test_stream_injects_mentions_into_prompt() -> None:
    service, _, agent, member_id = await build_service()
    events = [
        event
        async for event in service.stream(
            "给这个人记一条评价",
            mentions=[
                {"type": "member", "id": member_id, "label": "Alice"},
                {"type": "tool", "id": None, "label": "record_member_evaluation"},
            ],
        )
    ]
    assert events[-1]["type"] == "done"
    prompt = agent.prompts[0]
    assert f"member_id={member_id} 「Alice」" in prompt
    assert "tools to use: record_member_evaluation" in prompt
    assert "search_tools" in prompt

    plain_events = [event async for event in service.stream("普通消息")]
    assert "@-mentions" not in plain_events[-1] and "@-mentions" not in agent.prompts[-1]


def test_prepare_tools_defers_write_tools_and_keeps_read_tools() -> None:
    from pydantic_ai import Tool

    from progress.ai_tools import progress_ai_contribution
    from pulse.agent import prepare_tools

    tools = prepare_tools([progress_ai_contribution()])
    by_name = {}
    for item in tools:
        name = item.name if isinstance(item, Tool) else getattr(item, "__name__")
        by_name[name] = item
    assert set(by_name) >= {"list_tasks", "list_members", "create_task", "record_member_evaluation"}
    assert not isinstance(by_name["list_tasks"], Tool)
    assert isinstance(by_name["create_task"], Tool)
    assert by_name["create_task"].defer_loading is True
    assert isinstance(by_name["record_member_evaluation"], Tool)
    assert by_name["record_member_evaluation"].defer_loading is True


async def test_deferred_tool_is_discovered_via_search_then_callable() -> None:
    from pydantic_ai import Tool
    from pydantic_ai import Agent as PAAgent
    from pydantic_ai.capabilities import ToolSearch
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.test import TestModel
    from pydantic_ai.tools import RunContext

    called: list[str] = []

    async def list_tasks() -> list[str]:
        return ["task-1"]

    async def create_task(ctx: RunContext, title: str) -> dict:
        called.append(title)
        return {"queued": True}

    class SearchThenCallModel(TestModel):
        def __init__(self):
            super().__init__()
            self.step = 0
            self.visibilities = []

        def _request(self, messages, model_settings, model_request_parameters):
            self.step += 1
            self.visibilities.append(model_request_parameters.visibility_of("create_task"))
            if self.step == 1:
                return ModelResponse(parts=[ToolCallPart("search_tools", {"queries": ["create task"]})])
            if self.step == 2:
                return ModelResponse(parts=[ToolCallPart("create_task", {"title": "MYAI 联调"})])
            return ModelResponse(parts=[TextPart(content="已排队")])

    model = SearchThenCallModel()
    agent = PAAgent(
        model,
        deps_type=str,
        tools=[list_tasks, Tool(create_task, defer_loading=True)],
        capabilities=[ToolSearch()],
    )
    result = await agent.run("建一个任务")
    assert model.visibilities == ["withheld", "visible", "visible"]
    assert called == ["MYAI 联调"]
    assert result.output == "已排队"


async def test_create_task_tool_rejects_invalid_schedule() -> None:
    progress = ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository())
    ctx = SimpleNamespace(deps=AgentDeps(progress=progress))
    with pytest.raises(ModelRetry, match="start_date"):
        await create_task(
            ctx,
            title="Bad",
            start_date=date(2026, 9, 10),
            due_date=date(2026, 9, 1),
        )


async def test_ai_stream_issues_preview_token_then_confirm_writes() -> None:
    service, _, agent, member_id = await build_service()
    agent.pending = [
        {
            "op": "create_task",
            "changes": {"title": "Design UI", "assignee_id": member_id, "progress": 20},
        }
    ]
    events = [event async for event in service.stream("让 Alice 设计界面")]
    assert events[0]["type"] == "text"
    done = events[-1]
    assert done["type"] == "done"
    assert done["confirmation_token"]
    assert done["operations"][0]["changes"]["assignee_id"] == member_id
    confirmed = await service.confirm(done["confirmation_token"], "admin")
    assert confirmed[0]["title"] == "Design UI"
    assert confirmed[0]["progress"] == 20
    assert "让 Alice" in agent.prompts[0]
    assert "Asia/Shanghai" in agent.prompts[0]
    assert "last week Monday=" in agent.prompts[0]


async def test_ai_stream_cancel_skips_confirm_token() -> None:
    service, _, _, _ = await build_service(
        events=[{"type": "text", "delta": "部分回复"}],
        pending=[{"op": "create_task", "changes": {"title": "不应写入"}}],
    )
    cancel = CancellationToken()
    cancel.cancel()
    events = [event async for event in service.stream("卡住了", cancellation_token=cancel)]
    assert events == [{"type": "cancelled", "message": "已中断"}]


async def test_ai_stream_cancel_after_partial_text_does_not_issue_token() -> None:
    class CancellingAgent:
        async def stream(
            self,
            prompt: str,
            deps: AgentDeps,
            settings: object,
            cancellation_token: CancellationToken | None = None,
            message_history: list[object] | None = None,
        ) -> AsyncIterator[dict[str, object]]:
            assert settings and prompt
            yield {"type": "text", "delta": "开始"}
            assert cancellation_token
            cancellation_token.cancel()
            yield {"type": "text", "delta": "后续"}

    service, _, _, _ = await build_service()
    service.agent = CancellingAgent()
    events = [
        event async for event in service.stream("x", cancellation_token=CancellationToken())
    ]
    assert events[0] == {"type": "text", "delta": "开始"}
    assert events[-1] == {"type": "cancelled", "message": "已中断"}
    assert all(event.get("type") != "done" for event in events)


def test_clock_block_anchors_relative_weekdays() -> None:
    now = datetime(2026, 9, 1, 17, 36, tzinfo=ZoneInfo("Asia/Shanghai"))
    text = clock_block(now)
    assert "2026-09-01 17:36" in text
    assert "星期二" in text
    assert "This week Monday=2026-08-31" in text
    assert "last week Monday=2026-08-24" in text
    assert "next week Monday=2026-09-07" in text


async def test_add_entry_tool_matches_task_and_confirm_records_blocker() -> None:
    service, progress, agent, _ = await build_service()
    task = await progress.create({"title": "登录页", "status": "in_progress"}, "admin")
    ctx = SimpleNamespace(deps=AgentDeps(progress=progress))
    await add_progress_entry(ctx, kind="blocker", content="验证码服务超时", title_query="登录页")
    agent.pending = ctx.deps.pending
    events = [event async for event in service.stream("登录页卡在验证码超时")]
    done = events[-1]
    confirmed = await service.confirm(done["confirmation_token"], "admin")
    assert confirmed[0]["id"] == task.id
    assert confirmed[0]["entries"][0]["content"] == "验证码服务超时"


async def test_update_task_tool_uses_open_editor_context() -> None:
    progress = ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository())
    task = await progress.create({"title": "登录页", "status": "todo"}, "admin")
    ctx = SimpleNamespace(deps=AgentDeps(progress=progress, context_task_id=task.id))
    result = await update_task(ctx, status="in_progress")
    assert result["task_id"] == task.id
    assert ctx.deps.pending[0]["changes"]["status"] == "in_progress"


async def test_run_http_streams_events_and_does_not_write_until_confirm() -> None:
    from aiohttp.test_utils import TestClient, TestServer

    from app import create_app
    from shared.config import Settings

    agent = FakeProgressAgent(
        [
            {"type": "text", "delta": "将安排设计任务。"},
            {"type": "tool", "name": "create_task", "status": "start"},
        ],
        pending=[{"op": "create_task", "changes": {"title": "Design UI", "priority": "high"}}],
    )
    security = SecurityService("test-secret-with-at-least-32-characters", 60)
    app = create_app(
        Settings(admin_password="password123"),
        security=security,
        user_repository=MemoryUserRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        ai_repository=MemoryAISettingsRepository(),
        progress_agent=agent,
        resource_storage=MemoryResourceStorage(),
        **knowledge_overrides(),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "password123"}
        )
        headers = {"Authorization": f"Bearer {(await login.json())['access_token']}"}
        await client.put(
            "/api/v1/ai-settings",
            json={
                "base_url": "https://example.test/v1",
                "model": "test-model",
                "api_key": "secret-api-key",
            },
            headers=headers,
        )
        result = await client.post(
            "/api/v1/progress/ai/run",
            json={"instruction": "安排一个设计任务", "context_task_id": "task-open"},
            headers=headers,
        )
        assert result.status == 200
        payload = await result.text()
        events = [
            json.loads(line.removeprefix("data: "))
            for block in payload.strip().split("\n\n")
            for line in block.split("\n")
            if line.startswith("data: ")
        ]
        assert events[0]["delta"] == "将安排设计任务。"
        assert "将安排设计任务。" in payload
        assert events[1]["name"] == "create_task"
        done = events[-1]
        assert done["type"] == "done"
        assert done["operations"][0]["changes"]["title"] == "Design UI"
        listed = await client.get("/api/v1/progress/tasks", headers=headers)
        assert await listed.json() == []
        confirmed = await client.post(
            "/api/v1/progress/ai/confirm",
            json={"confirmation_token": done["confirmation_token"]},
            headers=headers,
        )
        assert confirmed.status == 200
        body = await confirmed.json()
        assert body[0]["title"] == "Design UI"
        assert "task_id=task-open" in agent.prompts[0]
    finally:
        await client.close()


async def test_progress_registers_ai_contribution() -> None:
    from app import create_app
    from shared.config import Settings
    from shared.web_keys import AI_CONTRIBUTIONS

    app = create_app(
        Settings(admin_password="password123"),
        security=SecurityService("test-secret-with-at-least-32-characters", 60),
        user_repository=MemoryUserRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        ai_repository=MemoryAISettingsRepository(),
        resource_storage=MemoryResourceStorage(),
        **knowledge_overrides(),
    )
    contribs = app[AI_CONTRIBUTIONS]
    assert [item.id for item in contribs] == ["progress", "knowledge"]
    assert [fn.__name__ for fn in contribs[0].tools] == [
        "list_tasks",
        "list_members",
        "get_task",
        "create_task",
        "update_task",
        "add_progress_entry",
        "create_member",
        "update_member",
        "record_member_evaluation",
        "create_project",
        "update_project",
    ]
