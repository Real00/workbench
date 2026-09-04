from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol

from pydantic_ai import Agent, CancellationToken, Tool
from pydantic_ai.capabilities import ToolSearch
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

from ai_settings.ports import AIConnectionSettings
from pulse.deps import AgentDeps
from shared.ai import ModuleAiContribution, compose_instructions
from shared.structured_llm import ai_model

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
}


def prepare_tools(contributions: Sequence[ModuleAiContribution]) -> list[Any]:
    """Wrap non-core tools with defer_loading so the model discovers them on demand."""
    tools: list[Any] = []
    for item in contributions:
        for fn in item.tools:
            if getattr(fn, "__name__", "") in ALWAYS_AVAILABLE_TOOLS:
                tools.append(fn)
            else:
                tools.append(Tool(fn, defer_loading=True))
    return tools


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

    async def stream(
        self,
        prompt: str,
        deps: AgentDeps,
        settings: AIConnectionSettings,
        cancellation_token: CancellationToken | None = None,
        message_history: Sequence[Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        tools = prepare_tools(self.contributions)
        instructions = compose_instructions(*(item.instructions for item in self.contributions))
        model = ai_model(settings)
        model_settings: OpenAIResponsesModelSettings | None = None
        if model.profile.get("openai_supports_reasoning"):
            model_settings = {"openai_reasoning_summary": "auto"}
        agent: Agent[AgentDeps, str] = Agent(
            model,
            name="pulse",
            deps_type=AgentDeps,
            output_type=str,
            tools=tools,
            instructions=instructions,
            model_settings=model_settings,
            capabilities=[ToolSearch()],
            retries=2,
        )
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
