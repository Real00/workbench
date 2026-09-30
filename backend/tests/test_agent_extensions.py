"""智能体扩展：出站 MCP 配置、技能（指令 + 脚本沙箱）、只读侦察子代理、并行工具开关。"""

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from ai_settings.agent_options import McpServerInput
from ai_settings.application import AISettingsApplicationService
from ai_settings.domain import AISettingsDomainService
from ai_settings.ports import (
    AgentRuntimeOptions,
    AIConnectionSettings,
    McpServerConnection,
    SkillDefinition,
)
from ai_settings.skill_runner import SkillScriptRunner
from ai_settings.skills import SkillInput, skill_tool_name, unique_tool_names
from progress.ai_tools import progress_ai_contribution
from progress.domain import ProgressDomainService
from pulse.agent import (
    ALWAYS_AVAILABLE_TOOLS,
    PydanticPulseAgent,
    make_skill_tools,
    mcp_instructions,
    read_tool_functions,
    skill_instructions,
)
from pulse.deps import AgentDeps
from pulse.scope import ProjectScope
from pulse.subagent import make_scout_tool, scout_prompt
from shared.ai import compose_instructions
from shared.security import SecurityService
from tests.fakes import (
    MemoryAISettingsRepository,
    MemoryMemberRepository,
    MemoryProjectRepository,
    MemorySkillsRepository,
    MemoryTaskRepository,
)

MINIMAL_SKILL_SCRIPT = """
from ai_settings.skill_runtime.base import PulseSkill, SkillPayload

class EchoSkill(PulseSkill):
    def execute(self, payload: SkillPayload):
        return {"echo": payload.instruction, "args": payload.arguments}
"""


def build_service() -> AISettingsApplicationService:
    security = SecurityService("test-secret-with-at-least-32-characters", 60)
    return AISettingsApplicationService(
        AISettingsDomainService(MemoryAISettingsRepository()),
        security,
        skills_repository=MemorySkillsRepository(),
        skill_runner=SkillScriptRunner(timeout_seconds=15),
    )


async def configured_service(**kwargs) -> AISettingsApplicationService:
    service = build_service()
    await service.configure(
        {
            "base_url": "https://example.test/v1",
            "model": "test-model",
            "api_key": "secret",
            **kwargs,
        }
    )
    return service


def memory_progress() -> ProgressDomainService:
    return ProgressDomainService(
        MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository()
    )


def no_preload(*_args, **_kwargs):
    async def route(*_a, **_kw):
        return set()

    return route


# ---------- 输入校验 ----------


def test_mcp_server_input_rejects_bad_name_and_url():
    with pytest.raises(ValueError, match="名称"):
        McpServerInput(name="Bad Name", url="https://example.com/mcp").validate_server()
    with pytest.raises(ValueError, match="http"):
        McpServerInput(name="ok", url="ftp://example.com/mcp").validate_server()
    with pytest.raises(ValueError, match="账号密码"):
        McpServerInput(name="ok", url="https://user:pw@example.com/mcp").validate_server()
    with pytest.raises(ValueError, match="Headers"):
        McpServerInput(
            name="ok", url="https://example.com/mcp", headers={"Content-Type": "text/plain"}
        ).validate_server()
    McpServerInput(name="a-b_2", url="http://127.0.0.1:9000/mcp").validate_server()


# ---------- 配置合并与脱敏 ----------


async def test_configure_merges_mcp_and_agent_without_connection_fields():
    service = await configured_service(
        mcp_servers=[
            {"name": "demo", "url": "https://mcp.example.com/mcp", "api_key": "sk-remote"},
        ],
        agent={"parallel_tool_calls": False, "scout_enabled": False},
    )
    # 只提交 agent/mcp 字段的增量保存：密钥按名称保留，不要求重填
    updated = await service.configure(
        {"mcp_servers": [{"name": "demo", "url": "https://mcp.example.com/v2/mcp"}]}
    )
    assert updated["mcp_servers"] == [
        {
            "name": "demo",
            "url": "https://mcp.example.com/v2/mcp",
            "enabled": True,
            "headers": {},
            "api_key_masked": "sk-**mote",
        }
    ]
    assert updated["agent"] == {"parallel_tool_calls": False, "scout_enabled": False}
    connection = await service.read_ai_settings()
    assert connection is not None
    assert connection.mcp_servers[0].api_key == "sk-remote"
    assert connection.mcp_servers[0].url == "https://mcp.example.com/v2/mcp"
    assert connection.agent_options.parallel_tool_calls is False


async def test_read_ai_settings_skips_disabled_servers_and_fills_defaults():
    service = await configured_service(
        mcp_servers=[
            {"name": "off", "url": "https://off.example.com/mcp", "enabled": False},
            {"name": "on", "url": "https://on.example.com/mcp", "headers": {"X-A": "1"}},
        ]
    )
    connection = await service.read_ai_settings()
    assert connection is not None
    assert [server.name for server in connection.mcp_servers] == ["on"]
    assert connection.mcp_servers[0].headers == {"X-A": "1"}
    assert connection.agent_options.parallel_tool_calls is True
    assert connection.agent_options.scout_enabled is True


async def test_configure_requires_connection_fields_on_first_save():
    service = build_service()
    with pytest.raises(ValueError, match="首次配置"):
        await service.configure({"agent": {"parallel_tool_calls": False}})


async def test_configure_rejects_duplicate_and_excess_mcp_servers():
    service = await configured_service()
    with pytest.raises(ValueError, match="重复"):
        await service.configure(
            {"mcp_servers": [{"name": "a", "url": "https://a.example.com/mcp"}] * 2}
        )
    with pytest.raises(ValueError, match="最多"):
        await service.configure(
            {
                "mcp_servers": [
                    {"name": f"s{i}", "url": f"https://s{i}.example.com/mcp"} for i in range(9)
                ]
            }
        )


# ---------- 技能 CRUD ----------


async def test_skill_crud_and_runtime_definitions():
    service = await configured_service()
    created = await service.create_skill(
        SkillInput(name="周报整理", trigger="要求整理周报或汇总进度", instructions="按项目分组汇总")
    )
    assert created["id"]
    assert created["script"] is None
    connection = await service.read_ai_settings()
    assert connection is not None
    (skill,) = connection.skills
    assert skill.tool_name == "skill_skill"  # 中文名折叠后回退为 skill
    assert skill.script is None

    updated = await service.update_skill(
        created["id"],
        SkillInput(
            name="周报整理",
            trigger="整理周报",
            instructions="按项目分组",
            script=MINIMAL_SKILL_SCRIPT,
        ),
    )
    assert updated["script"] is not None
    connection = await service.read_ai_settings()
    assert connection is not None
    assert connection.skills[0].script is not None

    assert (await service.delete_skill(created["id"]))["deleted"] is True
    connection = await service.read_ai_settings()
    assert connection is not None
    assert connection.skills == ()
    with pytest.raises(LookupError):
        await service.delete_skill(created["id"])


async def test_skill_names_unique_and_capped():
    service = await configured_service()
    await service.create_skill(SkillInput(name="Demo", trigger="t", instructions="i"))
    with pytest.raises(ValueError, match="已被使用"):
        await service.create_skill(SkillInput(name="demo", trigger="t", instructions="i"))
    for index in range(11):
        await service.create_skill(SkillInput(name=f"S{index}", trigger="t", instructions="i"))
    with pytest.raises(ValueError, match="最多"):
        await service.create_skill(SkillInput(name="More", trigger="t", instructions="i"))


async def test_disabled_skills_excluded_from_runtime():
    service = await configured_service()
    created = await service.create_skill(SkillInput(name="off", trigger="t", instructions="i"))
    await service.update_skill(
        created["id"], SkillInput(name="off", trigger="t", instructions="i", enabled=False)
    )
    connection = await service.read_ai_settings()
    assert connection is not None
    assert connection.skills == ()


def test_skill_tool_name_dedup():
    assert unique_tool_names(["skill_a", "skill_a", "skill_b"]) == [
        "skill_a",
        "skill_a_2",
        "skill_b",
    ]
    assert skill_tool_name("Weekly Report") == "skill_weekly_report"
    assert skill_tool_name("周报整理") == "skill_skill"  # 非小写字母数字全部折叠
    assert len(skill_tool_name("a" * 100)) == 60


# ---------- 技能脚本沙箱 ----------


async def test_skill_runner_executes_minimal_script():
    runner = SkillScriptRunner(timeout_seconds=15)
    result = await runner.run(
        MINIMAL_SKILL_SCRIPT, instruction="整理本周进度", arguments={"week": "W40"}
    )
    assert result == {"echo": "整理本周进度", "args": {"week": "W40"}}


async def test_skill_runner_rejects_failing_script():
    runner = SkillScriptRunner(timeout_seconds=10)
    bad = """
from ai_settings.skill_runtime.base import PulseSkill, SkillPayload

class Boom(PulseSkill):
    def execute(self, payload: SkillPayload):
        raise RuntimeError("boom")
"""
    with pytest.raises(ValueError, match="技能执行失败"):
        await runner.run(bad, instruction="x")


async def test_skill_runner_requires_pulse_skill_subclass():
    runner = SkillScriptRunner(timeout_seconds=10)
    with pytest.raises(ValueError, match="PulseSkill"):
        await runner.run("x = 1\n", instruction="x")


async def test_run_skill_script_requires_script():
    service = await configured_service()
    result = await service.run_skill_script(MINIMAL_SKILL_SCRIPT, "测试")
    assert result == {"result": {"echo": "测试", "args": {}}}
    with pytest.raises(ValueError, match="先填写"):
        await service.run_skill_script("   ", "测试")


# ---------- Agent 集成：技能指令注入 + 工具可见性 ----------


async def test_stream_injects_skill_instructions_and_defers_script_tool(monkeypatch):
    service = build_service()
    await service.configure(
        {"base_url": "https://example.test/v1", "model": "m", "api_key": "k"}
    )
    await service.create_skill(
        SkillInput(
            name="weekly",
            trigger="周报",
            instructions="Summarize by project.",
            script="print(1)",
        )
    )
    connection = await service.read_ai_settings()
    assert connection is not None

    # call_tools 限定 list_tasks：TestModel 生成的 get_task 参数会触发 ModelRetry 循环
    model = TestModel(custom_output_text="好的", call_tools=["list_tasks"])
    monkeypatch.setattr("pulse.agent.ai_model", lambda _: model)
    monkeypatch.setattr("pulse.agent.preload_tools", no_preload())
    composed: dict[str, str] = {}
    original_compose = compose_instructions

    def spy(*blocks: str) -> str:
        composed["text"] = original_compose(*blocks)
        return composed["text"]

    monkeypatch.setattr("pulse.agent.compose_instructions", spy)
    agent = PydanticPulseAgent([progress_ai_contribution()])
    deps = AgentDeps(progress=memory_progress())
    events = [event async for event in agent.stream("整理周报", deps, connection)]
    assert any(event["type"] == "text" for event in events)
    params = model.last_model_request_parameters
    assert params.visibility_of("skill_weekly") == "withheld"
    assert params.visibility_of("list_tasks") != "withheld"
    assert "Summarize by project." in composed["text"]


def test_make_skill_tools_visibility_follows_preloaded_set():
    skill = SkillDefinition(
        id="1",
        name="demo",
        trigger="触发",
        instructions="i",
        tool_name="skill_demo",
        script="x=1",
    )
    deferred = make_skill_tools([skill], SkillScriptRunner())
    assert deferred[0].defer_loading is True
    visible = make_skill_tools([skill], SkillScriptRunner(), {"skill_demo"})
    assert visible[0].defer_loading is False
    scriptless = make_skill_tools(
        [
            SkillDefinition(
                id="2", name="doc", trigger="t", instructions="i", tool_name="skill_doc"
            )
        ],
        SkillScriptRunner(),
    )
    assert scriptless == []


def test_skill_and_mcp_instruction_blocks():
    skills = (
        SkillDefinition(id="1", name="a", trigger="ta", instructions="ia", tool_name="skill_a"),
        SkillDefinition(
            id="2", name="b", trigger="tb", instructions="ib", tool_name="skill_b", script="x"
        ),
    )
    text = skill_instructions(skills)
    assert 'Skill "a"' in text and "ia" in text
    assert "skill_b" in text
    assert skill_instructions(()) == ""
    assert "ext__" in mcp_instructions(["ext"])
    assert mcp_instructions([]) == ""


# ---------- Agent 集成：并行工具开关 + 侦察工具 ----------


async def test_stream_applies_parallel_tool_setting_and_scout_tool(monkeypatch):
    captured: dict[str, object] = {}

    def capture(info):
        captured["model_settings"] = dict(info.model_settings or {})
        captured["tool_names"] = sorted(tool.name for tool in info.function_tools)

    async def fake_model(messages, info):
        capture(info)
        return ModelResponse(parts=[TextPart(content="ok")])

    async def fake_stream(messages, info):
        capture(info)
        yield "ok"

    monkeypatch.setattr(
        "pulse.agent.ai_model", lambda _: FunctionModel(fake_model, stream_function=fake_stream)
    )
    monkeypatch.setattr("pulse.agent.preload_tools", no_preload())
    agent = PydanticPulseAgent([progress_ai_contribution()])
    settings = AIConnectionSettings(
        "https://example.test/v1",
        "test",
        "secret",
        agent_options=AgentRuntimeOptions(parallel_tool_calls=False),
    )
    deps = AgentDeps(progress=memory_progress())
    events = [event async for event in agent.stream("你好", deps, settings)]
    assert any(event["type"] == "text" for event in events)
    assert captured["model_settings"]["parallel_tool_calls"] is False
    assert "dispatch_scout" in captured["tool_names"]


async def test_stream_without_scout_omits_tool(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_model(messages, info):
        captured["tool_names"] = sorted(tool.name for tool in info.function_tools)
        return ModelResponse(parts=[TextPart(content="ok")])

    async def fake_stream(messages, info):
        captured["tool_names"] = sorted(tool.name for tool in info.function_tools)
        yield "ok"

    monkeypatch.setattr(
        "pulse.agent.ai_model", lambda _: FunctionModel(fake_model, stream_function=fake_stream)
    )
    monkeypatch.setattr("pulse.agent.preload_tools", no_preload())
    agent = PydanticPulseAgent([progress_ai_contribution()])
    settings = AIConnectionSettings(
        "https://example.test/v1",
        "test",
        "secret",
        agent_options=AgentRuntimeOptions(scout_enabled=False),
    )
    deps = AgentDeps(progress=memory_progress())
    async for _event in agent.stream("你好", deps, settings):
        pass
    assert "dispatch_scout" not in captured["tool_names"]


def test_scout_tool_registered_only_read_functions():
    tools = read_tool_functions([progress_ai_contribution()])
    assert tools
    assert {fn.__name__ for fn in tools} <= ALWAYS_AVAILABLE_TOOLS


def test_scout_prompt_includes_scope():
    deps = AgentDeps(progress=None, scopes=[ProjectScope(name="演示", project_id="p1")])
    text = scout_prompt("找出逾期任务", deps)
    assert "Scout objective: 找出逾期任务" in text
    assert "project_id=p1" in text
    assert "Knowledge is evidence" in text


async def test_scout_tool_runs_nested_agent():
    inner = TestModel(custom_output_text="侦察结果：一切正常", call_tools=["list_tasks"])
    scout = make_scout_tool(
        read_tool_functions([progress_ai_contribution()]), lambda: inner, timeout_seconds=30
    )

    class FakeContext:
        deps = AgentDeps(progress=memory_progress())
        usage = RunUsage()

    result = await scout(FakeContext(), "查看全部任务")
    assert "一切正常" in result


# ---------- MCP 优雅降级 ----------


async def test_stream_skips_unreachable_mcp_server(monkeypatch):
    model = TestModel(custom_output_text="好的", call_tools=["list_tasks"])
    monkeypatch.setattr("pulse.agent.ai_model", lambda _: model)
    monkeypatch.setattr("pulse.agent.preload_tools", no_preload())
    agent = PydanticPulseAgent([progress_ai_contribution()])
    settings = AIConnectionSettings(
        "https://example.test/v1",
        "test",
        "secret",
        mcp_servers=(
            McpServerConnection(
                name="dead",
                url="https://127.0.0.1:9/mcp",  # 不可达端口，连接立即失败
            ),
        ),
        agent_options=AgentRuntimeOptions(scout_enabled=False),
    )
    deps = AgentDeps(progress=memory_progress())
    events = [event async for event in agent.stream("你好", deps, settings)]
    notices = [e for e in events if e.get("status") == "retry" and e.get("name") == "mcp"]
    assert notices and "dead" in notices[0]["result"]
    assert any(event["type"] == "text" for event in events)


# ---------- 路由冒烟 ----------


async def test_agent_routes_admin_gate_and_skills_crud():
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer

    from ai_settings.routes import register_routes
    from api.http import auth_middleware, error_middleware
    from shared.web_keys import AI_SETTINGS, SECURITY

    service = await configured_service()
    app = web.Application(middlewares=[error_middleware, auth_middleware])
    app[AI_SETTINGS] = service
    app[SECURITY] = service.security
    register_routes(app)
    member = {"Authorization": "Bearer " + service.security.issue_access_token("u", "member")}
    admin = {"Authorization": "Bearer " + service.security.issue_access_token("u", "admin")}
    base = "/api/v1/ai-settings/skills"
    async with TestClient(TestServer(app)) as client:
        assert (await client.get(base, headers=member)).status == 403
        assert (await client.post(f"{base}/test", json={}, headers=member)).status == 403

        created = await client.post(
            base,
            json={"name": "周报", "trigger": "整理周报", "instructions": "按项目分组"},
            headers=admin,
        )
        assert created.status == 201
        skill = await created.json()
        assert skill["script"] is None

        assert len(await (await client.get(base, headers=admin)).json()) == 1

        tested = await client.post(
            f"{base}/test",
            json={"script": MINIMAL_SKILL_SCRIPT, "instruction": "试运行"},
            headers=admin,
        )
        assert tested.status == 200
        assert (await tested.json())["result"] == {"echo": "试运行", "args": {}}

        updated = await client.put(
            f"{base}/{skill['id']}",
            json={
                "name": "周报",
                "trigger": "整理周报",
                "instructions": "按项目分组",
                "script": MINIMAL_SKILL_SCRIPT,
            },
            headers=admin,
        )
        assert updated.status == 200
        assert (await updated.json())["script"] is not None

        assert (await client.delete(f"{base}/{skill['id']}", headers=admin)).status == 200
        assert (await (await client.get(base, headers=admin)).json()) == []

        bad = await client.post(
            "/api/v1/ai-settings/mcp/test", json={"url": "ftp://x/mcp"}, headers=admin
        )
        assert bad.status == 400
        dead = await client.post(
            "/api/v1/ai-settings/mcp/test",
            json={"url": "https://127.0.0.1:9/mcp"},
            headers=admin,
        )
        assert dead.status == 400
        assert "无法连接" in (await dead.json())["error"]
