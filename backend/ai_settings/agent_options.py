"""智能体扩展配置的输入模型：出站 MCP 服务器与运行开关。"""

import re
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

# 服务器名同时用作工具前缀 `<name>__tool`，必须满足工具命名约束
SERVER_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
MAX_MCP_SERVERS = 8


class McpServerInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str
    url: str
    enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    api_key: str | None = None

    def validate_server(self) -> None:
        if not SERVER_NAME_PATTERN.match(self.name):
            raise ValueError(
                "MCP 服务器名称须以小写字母开头，仅含小写字母 / 数字 / - / _（不超过 32 字符）"
            )
        url = urlsplit(self.url)
        if url.scheme not in ("http", "https") or not url.hostname:
            raise ValueError("MCP 地址必须是 http(s) Streamable HTTP 端点")
        if url.username or url.password or url.query or url.fragment:
            raise ValueError("MCP 地址不能携带账号密码、查询参数或片段")
        lowered = {key.lower() for key in self.headers}
        if "content-type" in lowered or "content-length" in lowered:
            raise ValueError("Headers 不能覆盖 Content-Type / Content-Length")
        if len(self.headers) > 8:
            raise ValueError("自定义 Headers 最多 8 个")


class AgentOptionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parallel_tool_calls: bool = True
    scout_enabled: bool = True
