"""技能定义：名称 + 触发说明 + Markdown 指令，可选绑定一个可执行脚本工具。"""

import re

from pydantic import BaseModel, ConfigDict, Field

MAX_SKILLS = 12
MAX_SKILL_INSTRUCTION_CHARS = 8000
MAX_SKILL_SCRIPT_CHARS = 40_000
_SKILL_SLUG = re.compile(r"[^a-z0-9]+")


class SkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=48)
    trigger: str = Field(min_length=1, max_length=400)
    instructions: str = Field(min_length=1, max_length=MAX_SKILL_INSTRUCTION_CHARS)
    script: str | None = Field(default=None, max_length=MAX_SKILL_SCRIPT_CHARS)
    enabled: bool = True

    def model_post_init(self, __data: object | None = None) -> None:
        if self.script is not None and not self.script.strip():
            self.script = None


def skill_tool_name(name: str) -> str:
    """技能展示名 → 稳定的工具名（小写字母数字 + 下划线）。"""
    slug = _SKILL_SLUG.sub("_", name.lower()).strip("_") or "skill"
    return f"skill_{slug}"[:60]


def unique_tool_names(names: list[str]) -> list[str]:
    """同名技能展开为 skill_x / skill_x_2 …，保证注册到模型时不冲突。"""
    used: dict[str, int] = {}
    result: list[str] = []
    for name in names:
        used[name] = used.get(name, 0) + 1
        result.append(name if used[name] == 1 else f"{name}_{used[name]}")
    return result
