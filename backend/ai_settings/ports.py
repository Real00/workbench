from dataclasses import dataclass, field
from typing import Protocol

from ai_settings.jev import JevConnectionSettings


@dataclass(frozen=True)
class McpServerConnection:
    """已启用的远程 MCP 服务器（Streamable HTTP），供出站工具集连接。"""

    name: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    api_key: str = ""


@dataclass(frozen=True)
class AgentRuntimeOptions:
    parallel_tool_calls: bool = True
    scout_enabled: bool = True


@dataclass(frozen=True)
class SkillDefinition:
    """本轮对话可用的技能：指令注入 + 可选的可执行脚本工具。"""

    id: str
    name: str
    trigger: str
    instructions: str
    tool_name: str
    script: str | None = None


@dataclass(frozen=True)
class AIConnectionSettings:
    base_url: str
    model: str
    api_key: str
    jev: JevConnectionSettings | None = None
    mcp_servers: tuple[McpServerConnection, ...] = ()
    agent_options: AgentRuntimeOptions = AgentRuntimeOptions()
    skills: tuple[SkillDefinition, ...] = ()


class AISettingsReader(Protocol):
    async def read_ai_settings(self) -> AIConnectionSettings | None: ...
