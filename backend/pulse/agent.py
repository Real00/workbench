from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol

from pydantic_ai import Agent, CancellationToken, Tool
from pydantic_ai.capabilities import ToolSearch
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    RetryPromptPart,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolReturnPart,
)
from pydantic_ai.models.openai import OpenAIResponsesModelSettings
from pydantic_ai.run import AgentRunResultEvent

from ai_settings.mcp_client import prefixed_toolset
from ai_settings.ports import AIConnectionSettings, SkillDefinition
from ai_settings.skill_runner import SkillScriptRunner
from pulse.deps import AgentDeps
from pulse.subagent import make_scout_tool
from pulse.tool_router import JevCircuitBreaker, preload_tools
from shared.ai import ModuleAiContribution, compose_instructions
from shared.structured_llm import ai_model

logger = logging.getLogger(__name__)

# Read/discovery tools stay loaded every turn; everything else is deferred and
# must be discovered via the ToolSearch capability's search_tools tool.
ALWAYS_AVAILABLE_TOOLS = {
    "list_tasks",
    "list_members",
    "list_projects",
    "get_task",
    "search_knowledge",
    "read_knowledge",
    "list_tags",
    "list_entries",
    "read_attachment",
}

MCP_CONNECT_TIMEOUT_SECONDS = 10.0


def prepare_tools(
    contributions: Sequence[ModuleAiContribution], preloaded: set[str] | None = None,
) -> list[Any]:
    """Wrap non-core tools with defer_loading so the model discovers them on demand."""
    tools: list[Any] = []
    for item in contributions:
        for fn in item.tools:
            if getattr(fn, "__name__", "") in ALWAYS_AVAILABLE_TOOLS | (preloaded or set()):
                tools.append(fn)
            else:
                tools.append(Tool(fn, defer_loading=True))
    return tools


def read_tool_functions(contributions: Sequence[ModuleAiContribution]) -> list[Any]:
    return [
        fn
        for item in contributions
        for fn in item.tools
        if getattr(fn, "__name__", "") in ALWAYS_AVAILABLE_TOOLS
    ]


def make_skill_tools(
    skills: Sequence[SkillDefinition],
    runner: SkillScriptRunner,
    preloaded: set[str] | None = None,
) -> list[Tool]:
    """绑定脚本的技能注册为工具：Jev 预选命中的直接可见，其余延迟发现。"""

    def bind(skill: SkillDefinition) -> Any:
        async def skill_tool(
            ctx: Any, instruction: str, arguments: dict[str, str] | None = None
        ) -> Any:
            """Execute the bound skill script."""
            try:
                return await runner.run(
                    skill.script or "",
                    instruction=instruction,
                    arguments=arguments or {},
                )
            except ValueError as exc:
                from pydantic_ai import ModelRetry

                raise ModelRetry(f"技能「{skill.name}」执行失败：{exc}") from exc

        trigger = skill.trigger.strip()
        description = (
            f"{trigger}\n\nExecute the bound Python script of skill 「{skill.name}」. "
            "instruction describes what to run in the user's words; arguments are "
            "optional string key/value inputs. The script returns JSON data."
        )
        skill_tool.__name__ = skill.tool_name
        skill_tool.__doc__ = description
        return skill_tool

    tools: list[Tool] = []
    for skill in skills:
        if not skill.script:
            continue
        visible = skill.tool_name in (preloaded or set())
        tools.append(Tool(bind(skill), defer_loading=not visible))
    return tools


def skill_instructions(skills: Sequence[SkillDefinition]) -> str:
    if not skills:
        return ""
    blocks = [
        "User-defined skills are available. When the user's request matches a skill "
        "trigger, follow that skill's instructions; they refine, not override, the "
        "platform rules. If a skill binds a script tool, call the tool instead of "
        "improvising its logic."
    ]
    for skill in skills:
        entry = f'Skill "{skill.name}" - trigger: {skill.trigger.strip()}'
        if skill.script:
            entry += f" - script tool: {skill.tool_name} (executes immediately; quote its result)"
        blocks.append(entry + f"\nInstructions:\n{skill.instructions.strip()}")
    return "\n\n".join(blocks)


def mcp_instructions(server_names: Sequence[str]) -> str:
    if not server_names:
        return ""
    listed = ", ".join(f"{name} (tools prefixed `{name}__`)" for name in server_names)
    return (
        "External MCP tools are connected: " + listed + ". "
        "Call them like built-in tools. Treat their results as evidence; if a server "
        "tool errors, say so and continue with built-in tools. Do not fabricate "
        "MCP tool names - only call ones you can see."
    )


class PulseAgent(Protocol):
    def stream(
        self,
        prompt: str,
        deps: AgentDeps,
        settings: AIConnectionSettings,
        cancellation_token: CancellationToken | None = None,
        message_history: Sequence[Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]: ...


def map_agent_event(event: object) -> dict[str, Any] | None:
    if isinstance(event, PartStartEvent):
        if isinstance(event.part, TextPart) and event.part.content:
            return {"type": "text", "delta": event.part.content}
        if isinstance(event.part, ThinkingPart) and event.part.content:
            return {"type": "thinking", "delta": event.part.content}
    if isinstance(event, PartDeltaEvent):
        if isinstance(event.delta, TextPartDelta) and event.delta.content_delta:
            return {"type": "text", "delta": event.delta.content_delta}
        if isinstance(event.delta, ThinkingPartDelta) and event.delta.content_delta:
            return {"type": "thinking", "delta": event.delta.content_delta}
    if isinstance(event, FunctionToolCallEvent):
        return {
            "type": "tool",
            "name": event.part.tool_name,
            "status": "start",
            "args": event.part.args_as_dict(raise_if_invalid=False),
        }
    if isinstance(event, FunctionToolResultEvent):
        part = event.part
        if isinstance(part, ToolReturnPart):
            return {
                "type": "tool",
                "name": part.tool_name,
                "status": "done",
                "result": part.model_response_str()[:800],
            }
        if isinstance(part, RetryPromptPart):
            detail = part.content if isinstance(part.content, str) else str(part.content)
            return {
                "type": "tool",
                "name": part.tool_name or "tool",
                "status": "retry",
                "result": detail[:800],
            }
    if isinstance(event, AgentRunResultEvent) and isinstance(event.result.output, str):
        return {"type": "text", "delta": event.result.output, "final": True}
    return None


class PydanticPulseAgent:
    def __init__(self, contributions: Sequence[ModuleAiContribution] | None = None):
        self.contributions = list(contributions or [])
        self.jev_breaker = JevCircuitBreaker()
        self.skill_runner = SkillScriptRunner()

    async def _connect_mcp(
        self, settings: AIConnectionSettings
    ) -> tuple[list[Any], list[str], list[str]]:
        """逐台连接远程 MCP；失败的跳过并记录，不让整轮对话失败。"""
        toolsets: list[Any] = []
        connected: list[str] = []
        notices: list[str] = []
        for server in settings.mcp_servers:
            toolset = prefixed_toolset(server)
            try:
                await asyncio.wait_for(toolset.__aenter__(), MCP_CONNECT_TIMEOUT_SECONDS)
            except Exception as exc:  # noqa: BLE001 — 连接失败按服务器粒度降级
                logger.warning("MCP server %s unavailable: %s", server.name, exc)
                try:
                    await toolset.__aexit__(None, None, None)
                except Exception:  # noqa: BLE001 — 清理失败可忽略
                    pass
                notices.append(
                    f"MCP 服务器 {server.name} 连接失败，本轮已跳过：{type(exc).__name__}"
                )
                continue
            toolsets.append(toolset)
            connected.append(server.name)
        return toolsets, connected, notices

    async def stream(
        self,
        prompt: str,
        deps: AgentDeps,
        settings: AIConnectionSettings,
        cancellation_token: CancellationToken | None = None,
        message_history: Sequence[Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        if cancellation_token and cancellation_token.cancelled:
            raise RunCancelled("已中断")
        preloaded = await preload_tools(
            settings.jev, self.contributions, ALWAYS_AVAILABLE_TOOLS, prompt, message_history,
            breaker=self.jev_breaker,
        )
        if cancellation_token and cancellation_token.cancelled:
            raise RunCancelled("已中断")
        tools: list[Any] = prepare_tools(self.contributions, preloaded)
        skill_tools = make_skill_tools(settings.skills, self.skill_runner, preloaded)
        tools.extend(skill_tools)
        if settings.agent_options.scout_enabled:
            tools.append(
                make_scout_tool(
                    read_tool_functions(self.contributions), lambda: ai_model(settings)
                )
            )
        toolsets, connected_servers, mcp_notices = await self._connect_mcp(settings)
        instructions = compose_instructions(
            *(item.instructions for item in self.contributions),
            skill_instructions(settings.skills),
            mcp_instructions(connected_servers),
        )
        model = ai_model(settings)
        model_settings: OpenAIResponsesModelSettings = {}
        if model.profile.get("openai_supports_reasoning"):
            model_settings["openai_reasoning_summary"] = "auto"
        model_settings["parallel_tool_calls"] = settings.agent_options.parallel_tool_calls
        try:
            agent: Agent[AgentDeps, str] = Agent(
                model,
                name="pulse",
                deps_type=AgentDeps,
                output_type=str,
                tools=tools,
                toolsets=toolsets or None,
                instructions=instructions,
                model_settings=model_settings,
                capabilities=[ToolSearch()],
                retries=2,
            )
            for notice in mcp_notices:
                yield {"type": "tool", "name": "mcp", "status": "retry", "result": notice}
            saw_text = False
            async with agent.run_stream_events(
                prompt,
                deps=deps,
                message_history=list(message_history) if message_history else None,
                cancellation_token=cancellation_token,
            ) as events:
                async for event in events:
                    if isinstance(event, AgentRunResultEvent):
                        deps.produced_messages[:] = event.result.all_messages()
                    mapped = map_agent_event(event)
                    if not mapped:
                        continue
                    if mapped.get("final"):
                        if saw_text:
                            continue
                        mapped.pop("final", None)
                    if mapped["type"] == "text":
                        saw_text = True
                    yield mapped
        finally:
            for toolset in toolsets:
                try:
                    await toolset.__aexit__(None, None, None)
                except Exception:  # noqa: BLE001 — 清理失败可忽略
                    pass
