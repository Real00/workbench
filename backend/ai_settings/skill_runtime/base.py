"""技能脚本契约：子类化 PulseSkill 并实现 execute。

脚本由 SkillScriptRunner 放进白名单子进程执行（无网络隔离，30s 超时），
execute 的返回值必须是可 JSON 序列化的对象。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillPayload:
    instruction: str
    arguments: dict[str, str] = field(default_factory=dict)


class PulseSkill(ABC):
    @abstractmethod
    def execute(self, payload: SkillPayload) -> Any: ...
