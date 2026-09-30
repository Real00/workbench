import asyncio
from dataclasses import asdict
from typing import Any

from openai import APITimeoutError
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior

from ai_settings.agent_options import MAX_MCP_SERVERS, AgentOptionsInput, McpServerInput
from ai_settings.domain import AISettingsDomainService
from ai_settings.jev import JEV_MAX_TIMEOUT_SECONDS, JevConnectionSettings, JevInput, JevOptions
from ai_settings.mcp_client import probe_mcp_server
from ai_settings.ports import (
    AgentRuntimeOptions,
    AIConnectionSettings,
    McpServerConnection,
    SkillDefinition,
)
from ai_settings.skill_runner import SkillScriptRunner
from ai_settings.skills import MAX_SKILLS, SkillInput, skill_tool_name, unique_tool_names
from shared.jev import evaluate_tools
from shared.model_errors import model_error_message
from shared.security import SecurityService, mask_secret
from shared.structured_llm import ai_model


class AISettingsApplicationService:
    def __init__(
        self,
        domain: AISettingsDomainService,
        security: SecurityService,
        skills_repository: Any | None = None,
        skill_runner: SkillScriptRunner | None = None,
    ):
        self.domain = domain
        self.security = security
        self.skills_repository = skills_repository
        self.skill_runner = skill_runner or SkillScriptRunner()

    async def initialize(self) -> None:
        await self.domain.ensure_indexes()
        if self.skills_repository is not None:
            await self.skills_repository.ensure_indexes()

    async def configure(self, data: dict[str, Any]) -> dict[str, Any]:
        current = await self.domain.get()
        if not current and not (data.get("base_url") and data.get("model")):
            raise ValueError("首次配置需要填写 base_url 与 model")
        base_url = data.get("base_url") or (current.base_url if current else "")
        model = data.get("model") or (current.model if current else "")
        api_key = data.get("api_key")
        if not api_key and current:
            encrypted = current.encrypted_api_key
        elif api_key:
            encrypted = self.security.encrypt(api_key)
        else:
            raise ValueError("api_key is required")
        jev = current.jev if current else None
        if data.get("jev") is not None:
            jev = self._prepare_jev(data["jev"], jev)
        mcp_servers = list(current.mcp_servers or []) if current else []
        if data.get("mcp_servers") is not None:
            mcp_servers = self._prepare_mcp_servers(data["mcp_servers"], mcp_servers)
        agent = current.agent if current else None
        if data.get("agent") is not None:
            agent = self._prepare_agent_options(data["agent"])
        settings = await self.domain.configure(
            base_url, model, encrypted, jev, mcp_servers, agent
        )
        return self._public(settings)

    async def get(self) -> dict[str, Any] | None:
        settings = await self.domain.get()
        return self._public(settings) if settings else None

    async def get_secret(self) -> dict[str, str]:
        settings = await self.domain.get()
        if not settings:
            raise LookupError("AI settings not configured")
        return {"api_key": self.security.decrypt(settings.encrypted_api_key)}

    async def read_ai_settings(self) -> AIConnectionSettings | None:
        settings = await self.domain.get()
        if not settings:
            return None
        skills = await self.active_skills()
        return AIConnectionSettings(
            base_url=settings.base_url,
            model=settings.model,
            api_key=self.security.decrypt(settings.encrypted_api_key),
            jev=self._jev_connection(settings.jev),
            mcp_servers=tuple(self._mcp_connections(settings.mcp_servers)),
            agent_options=self._runtime_options(settings.agent),
            skills=skills,
        )

    async def active_skills(self) -> tuple[SkillDefinition, ...]:
        if self.skills_repository is None:
            return ()
        records = [record for record in await self.skills_repository.list() if record.enabled]
        tool_names = unique_tool_names([skill_tool_name(record.name) for record in records])
        return tuple(
            SkillDefinition(
                id=record.id,
                name=record.name,
                trigger=record.trigger,
                instructions=record.instructions,
                tool_name=tool_name,
                script=record.script,
            )
            for record, tool_name in zip(records, tool_names, strict=True)
        )

    async def test_connection(self, override: dict[str, Any] | None = None) -> dict[str, Any]:
        settings = await self.domain.get()
        override = override or {}
        if not settings and not (override.get("api_key") and override.get("base_url")):
            raise LookupError("AI settings not configured")
        base_url = override.get("base_url") or (settings.base_url if settings else "")
        api_key = override.get("api_key") or self.security.decrypt(
            settings.encrypted_api_key if settings else ""
        )
        model = override.get("model") or (settings.model if settings else "")
        if not model.strip():
            raise ValueError("请填写要测试的模型名称")
        connection = AIConnectionSettings(base_url=base_url, model=model, api_key=api_key)
        agent = Agent(ai_model(connection), output_type=str)
        try:
            async with asyncio.timeout(45):
                async with agent.run_stream("Reply only OK.") as result:
                    output = await result.get_output()
                    if not output.strip():
                        raise ValueError("模型返回了空内容，请检查模型配置")
        except (UnexpectedModelBehavior, APITimeoutError) as exc:
            raise ValueError(model_error_message(exc)) from exc
        except TimeoutError as exc:
            raise ValueError("模型流式测试超时，请检查服务状态或稍后重试") from exc
        return {"ok": True, "model": model, "streaming": True}

    async def test_mcp_connection(self, override: dict[str, Any]) -> dict[str, Any]:
        draft = McpServerInput.model_validate(
            {"name": "probe", **override} if "name" not in override else override
        )
        draft.validate_server()
        tools = await probe_mcp_server(
            McpServerConnection(
                name=draft.name,
                url=draft.url,
                headers=dict(draft.headers),
                api_key=draft.api_key or "",
            )
        )
        return {"ok": True, "url": draft.url, "tools": tools}

    # ----- 技能 CRUD（设置页「智能体」分类） -----

    def _require_skills(self) -> Any:
        if self.skills_repository is None:
            raise ValueError("skills module is not available")
        return self.skills_repository

    async def list_skills(self) -> list[dict[str, Any]]:
        if self.skills_repository is None:
            return []
        return [record.public() for record in await self.skills_repository.list()]

    async def _assert_skill_free(self, name: str, exclude_id: str | None = None) -> None:
        repository = self._require_skills()
        for record in await repository.list():
            if record.name.casefold() == name.casefold() and record.id != exclude_id:
                raise ValueError(f"技能名称「{name}」已被使用")

    async def create_skill(self, data: SkillInput) -> dict[str, Any]:
        repository = self._require_skills()
        existing = await repository.list()
        if len(existing) >= MAX_SKILLS:
            raise ValueError(f"技能最多 {MAX_SKILLS} 个，请先删除不再使用的技能")
        await self._assert_skill_free(data.name)
        return (await repository.create(data)).public()

    async def update_skill(self, skill_id: str, data: SkillInput) -> dict[str, Any]:
        repository = self._require_skills()
        await self._assert_skill_free(data.name, exclude_id=skill_id)
        record = await repository.update(skill_id, data.model_dump())
        if record is None:
            raise LookupError("技能不存在")
        return record.public()

    async def delete_skill(self, skill_id: str) -> dict[str, Any]:
        if not await self._require_skills().delete(skill_id):
            raise LookupError("技能不存在")
        return {"deleted": True}

    async def run_skill_script(self, script: str, instruction: str) -> dict[str, Any]:
        if not script.strip():
            raise ValueError("请先填写技能脚本")
        result = await self.skill_runner.run(script, instruction=instruction)
        return {"result": result}

    def _prepare_jev(
        self,
        data: dict[str, Any],
        current: dict[str, Any] | None,
    ) -> dict[str, Any]:
        values = dict(current or {})
        if "timeout_seconds" in values:
            values["timeout_seconds"] = min(values["timeout_seconds"], JEV_MAX_TIMEOUT_SECONDS)
        encrypted = values.pop("encrypted_api_key", "")
        values.update(data)
        draft = JevInput.model_validate(values)
        draft.validate_connection()
        if draft.api_key:
            encrypted = self.security.encrypt(draft.api_key)
        if draft.enabled and not encrypted:
            raise ValueError("启用 Jev 需要填写独立的 TypeSafe API Key")
        return {
            **draft.model_dump(exclude={"api_key"}),
            "base_url": draft.base_url.rstrip("/"),
            "encrypted_api_key": encrypted,
        }

    def _prepare_mcp_servers(
        self,
        data: list[dict[str, Any]],
        current: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if len(data) > MAX_MCP_SERVERS:
            raise ValueError(f"MCP 服务器最多 {MAX_MCP_SERVERS} 个")
        stored = {item.get("name", ""): item for item in current}
        prepared: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in data:
            draft = McpServerInput.model_validate(raw)
            draft.validate_server()
            if draft.name in seen:
                raise ValueError(f"MCP 服务器名称重复：{draft.name}")
            seen.add(draft.name)
            encrypted = stored.get(draft.name, {}).get("encrypted_api_key", "")
            if draft.api_key:
                encrypted = self.security.encrypt(draft.api_key)
            prepared.append(
                {
                    "name": draft.name,
                    "url": draft.url,
                    "enabled": draft.enabled,
                    "headers": dict(draft.headers),
                    "encrypted_api_key": encrypted,
                }
            )
        return prepared

    def _prepare_agent_options(self, data: dict[str, Any]) -> dict[str, Any]:
        return AgentOptionsInput.model_validate(data).model_dump()

    def _mcp_connections(self, data: list[dict[str, Any]] | None) -> list[McpServerConnection]:
        connections: list[McpServerConnection] = []
        for item in data or []:
            if not item.get("enabled"):
                continue
            encrypted = item.get("encrypted_api_key", "")
            connections.append(
                McpServerConnection(
                    name=item["name"],
                    url=item["url"],
                    headers=dict(item.get("headers") or {}),
                    api_key=self.security.decrypt(encrypted) if encrypted else "",
                )
            )
        return connections

    def _runtime_options(self, data: dict[str, Any] | None) -> AgentRuntimeOptions:
        options = AgentOptionsInput.model_validate(data or {})
        return AgentRuntimeOptions(
            parallel_tool_calls=options.parallel_tool_calls,
            scout_enabled=options.scout_enabled,
        )

    def _jev_connection(self, data: dict[str, Any] | None) -> JevConnectionSettings | None:
        if not data or not data.get("enabled"):
            return None
        return JevConnectionSettings(
            base_url=data["base_url"],
            model=data["model"],
            api_key=self.security.decrypt(data["encrypted_api_key"]),
            threshold=data["threshold"],
            timeout_seconds=min(data["timeout_seconds"], JEV_MAX_TIMEOUT_SECONDS),
        )

    async def test_jev_connection(self, override: dict[str, Any]) -> dict[str, Any]:
        current = await self.domain.get()
        data = self._prepare_jev({**override, "enabled": True}, current.jev if current else None)
        connection = self._jev_connection(data)
        assert connection is not None
        await evaluate_tools(
            connection,
            {"request": "创建一个任务"},
            {"create_task": "Create a task with a title."},
        )
        return {"ok": True, "model": connection.model}

    def _public(self, settings: Any) -> dict[str, Any]:
        data = asdict(settings)
        key = self.security.decrypt(data.pop("encrypted_api_key"))
        data["api_key_masked"] = mask_secret(key)
        jev = data.get("jev") or JevOptions().model_dump()
        jev["timeout_seconds"] = min(jev["timeout_seconds"], JEV_MAX_TIMEOUT_SECONDS)
        jev_key = jev.pop("encrypted_api_key", "")
        jev["api_key_masked"] = mask_secret(self.security.decrypt(jev_key)) if jev_key else ""
        data["jev"] = jev
        servers = []
        for item in data.get("mcp_servers") or []:
            item = dict(item)
            encrypted = item.pop("encrypted_api_key", "")
            item["api_key_masked"] = (
                mask_secret(self.security.decrypt(encrypted)) if encrypted else ""
            )
            servers.append(item)
        data["mcp_servers"] = servers
        data["agent"] = AgentOptionsInput.model_validate(data.get("agent") or {}).model_dump()
        return data
