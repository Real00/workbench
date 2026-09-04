import asyncio
from collections import OrderedDict
from collections.abc import AsyncIterator, Sequence
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from pydantic_ai import CancellationToken
from pydantic_ai.exceptions import RunCancelled

from ai_settings.ports import AISettingsReader
from knowledge.application import KnowledgeApplicationService
from progress.domain import ProgressDomainService
from pulse.agent import PulseAgent, PydanticPulseAgent
from pulse.deps import AgentDeps
from shared.ai import ModuleAiContribution, clock_block
from shared.security import SecurityService

AI_STREAM_TIMEOUT_SECONDS = 240
_CANCELLED = {"type": "cancelled", "message": "已中断"}
_TIMED_OUT = {"type": "cancelled", "message": "请求超时，已中断"}
KNOWLEDGE_OPS = {
    "create_tag",
    "update_tag",
    "create_entry",
    "update_entry",
    "create_document",
    "update_document",
    "link_entry",
}
MAX_SESSIONS = 50
MAX_SESSION_EXCHANGES = 8

_MENTION_KINDS = {
    "task": "task_id",
    "member": "member_id",
    "project": "project_id",
    "document": "document_id",
}


def _mention_lines(mentions: list[dict[str, Any]] | None) -> str | None:
    if not mentions:
        return None
    lines: list[str] = []
    tools: list[str] = []
    for mention in mentions:
        kind = str(mention.get("type") or "")
        label = str(mention.get("label") or "").strip()
        if not label:
            continue
        if kind == "tool":
            tools.append(label)
            continue
        field = _MENTION_KINDS.get(kind)
        if field:
            identifier = str(mention.get("id") or "unknown")
            lines.append(f"- {field}={identifier} 「{label}」")
    if tools:
        lines.append("- tools to use: " + ", ".join(tools))
    if not lines:
        return None
    lines.append(
        "Treat these @-mentions as the user's intended references and prefer them over "
        "name guessing. If a mentioned tool is not visible yet, discover it with "
        "search_tools first."
    )
    return "The user @-mentioned:\n" + "\n".join(lines)


class PulseApplicationService:
    def __init__(
        self,
        settings_reader: AISettingsReader,
        progress_domain: ProgressDomainService,
        security: SecurityService,
        preview_ttl_seconds: int,
        agent: PulseAgent | None = None,
        knowledge: KnowledgeApplicationService | None = None,
        contributions: Sequence[ModuleAiContribution] | None = None,
    ):
        self.settings_reader = settings_reader
        self.progress_domain = progress_domain
        self.knowledge = knowledge
        self.security = security
        self.preview_ttl_seconds = preview_ttl_seconds
        self.contributions = list(contributions or [])
        self.agent = agent or PydanticPulseAgent(self.contributions)
        self._sessions: OrderedDict[str, list[Any]] = OrderedDict()

    def _resolve_session(self, session_id: str | None) -> tuple[str, list[Any]]:
        if session_id and session_id in self._sessions:
            self._sessions.move_to_end(session_id)
            return session_id, self._sessions[session_id]
        new_id = uuid4().hex[:12]
        self._sessions[new_id] = []
        while len(self._sessions) > MAX_SESSIONS:
            self._sessions.popitem(last=False)
        return new_id, self._sessions[new_id]

    def _store_session(self, session_id: str, messages: list[Any]) -> None:
        if not messages:
            return
        starts = [
            index
            for index, message in enumerate(messages)
            if hasattr(message, "parts")
            and any(type(part).__name__ == "UserPromptPart" for part in message.parts)
        ]
        if len(starts) > MAX_SESSION_EXCHANGES:
            messages = messages[starts[-MAX_SESSION_EXCHANGES]:]
        self._sessions[session_id] = messages
        self._sessions.move_to_end(session_id)

    async def stream(
        self,
        instruction: str,
        context_task_id: str | None = None,
        cancellation_token: CancellationToken | None = None,
        context_document_id: str | None = None,
        session_id: str | None = None,
        mentions: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        settings = await self.settings_reader.read_ai_settings()
        if not settings:
            yield {
                "type": "error",
                "message": "尚未配置 AI，请先在系统设置中填写模型与 API Key",
            }
            return
        active_session_id, history = self._resolve_session(session_id)
        deps = AgentDeps(
            progress=self.progress_domain,
            knowledge=None if self.knowledge is None else self.knowledge.domain,
            corpus=None if self.knowledge is None else self.knowledge.corpus,
            context_task_id=context_task_id,
            context_document_id=context_document_id,
        )
        parts = [clock_block()]
        if context_task_id:
            parts.append(f"The user is currently viewing task_id={context_task_id}.")
        if context_document_id:
            parts.append(f"The user is currently viewing document_id={context_document_id}.")
        mention_lines = _mention_lines(mentions)
        if mention_lines:
            parts.append(mention_lines)
        parts.append(instruction)
        prompt = "\n\n".join(parts)
        try:
            async with asyncio.timeout(AI_STREAM_TIMEOUT_SECONDS):
                async for event in self.agent.stream(
                    prompt,
                    deps,
                    settings,
                    cancellation_token,
                    message_history=history,
                ):
                    yield event
                    if cancellation_token and cancellation_token.cancelled:
                        yield dict(_CANCELLED)
                        return
        except TimeoutError:
            if cancellation_token:
                cancellation_token.cancel()
            yield dict(_TIMED_OUT)
            return
        except RunCancelled:
            yield dict(_CANCELLED)
            return
        except Exception as exc:
            yield {"type": "error", "message": f"AI run failed: {exc}"}
            return
        if cancellation_token and cancellation_token.cancelled:
            yield dict(_CANCELLED)
            return
        self._store_session(active_session_id, deps.produced_messages)
        token = None
        if deps.pending:
            token = self.security.issue_preview_token(
                {"operations": deps.pending},
                self.preview_ttl_seconds,
                purpose="progress-ai-preview",
            )
        yield {
            "type": "done",
            "confirmation_token": token,
            "operations": deps.pending,
            "session_id": active_session_id,
        }

    async def confirm(self, token: str, actor_id: str) -> list[dict[str, Any]]:
        payload = self.security.decode_token(token, "progress-ai-preview")
        operations = payload.get("operations") or []
        if not operations:
            raise ValueError("没有可应用的变更")
        results: list[dict[str, Any]] = []
        for operation in operations:
            op = operation.get("op")
            if op in KNOWLEDGE_OPS:
                if self.knowledge is None:
                    raise ValueError("knowledge module is not available")
                results.append(await self.knowledge.apply_operation(operation))
                continue
            if op == "create_task":
                results.append(
                    asdict(await self.progress_domain.create(operation["changes"], actor_id))
                )
            elif op == "update_task":
                results.append(
                    asdict(
                        await self.progress_domain.update(
                            operation["task_id"], operation.get("changes") or {}
                        )
                    )
                )
            elif op == "add_entry":
                results.append(
                    asdict(
                        await self.progress_domain.update(
                            operation["task_id"], {"add_entry": operation["entry"]}
                        )
                    )
                )
            elif op == "create_member":
                results.append(
                    asdict(await self.progress_domain.create_member(operation["changes"]))
                )
            elif op == "update_member":
                results.append(
                    asdict(
                        await self.progress_domain.update_member(
                            operation["member_id"], operation.get("changes") or {}
                        )
                    )
                )
            elif op == "add_member_evaluation":
                evaluation = operation.get("evaluation") or {}
                results.append(
                    asdict(
                        await self.progress_domain.add_member_evaluation(
                            operation["member_id"],
                            str(evaluation.get("kind") or "note"),
                            str(evaluation.get("content") or ""),
                        )
                    )
                )
            elif op == "create_project":
                results.append(
                    asdict(await self.progress_domain.create_project(operation["changes"]))
                )
            elif op == "update_project":
                results.append(
                    asdict(
                        await self.progress_domain.update_project(
                            operation["project_id"], operation.get("changes") or {}
                        )
                    )
                )
            else:
                raise ValueError(f"unknown AI operation: {op}")
        return results
