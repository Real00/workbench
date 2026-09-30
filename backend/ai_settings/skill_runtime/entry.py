#!/usr/bin/env python3
"""子进程入口：加载技能脚本中的 PulseSkill 子类并执行。

用法：python entry.py <script_path>
stdin: {"instruction": "...", "arguments": {...}}
stdout: {"result": <execute 返回值，须可 JSON 序列化>}
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import traceback
from pathlib import Path

# 保证能 import ai_settings.skill_runtime.base（由 runner 设置 PYTHONPATH）
from ai_settings.skill_runtime.base import PulseSkill, SkillPayload  # noqa: E402


def _load_skill(script_path: Path) -> PulseSkill:
    spec = importlib.util.spec_from_file_location("user_pulse_skill", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载技能脚本")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    skills: list[type[PulseSkill]] = []
    for value in vars(module).values():
        if (
            inspect.isclass(value)
            and issubclass(value, PulseSkill)
            and value is not PulseSkill
            and not inspect.isabstract(value)
        ):
            skills.append(value)
    if not skills:
        raise RuntimeError("脚本须定义 PulseSkill 子类")
    if len(skills) > 1:
        raise RuntimeError("脚本只能定义一个 PulseSkill 子类")
    return skills[0]()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: entry.py <script_path>", file=sys.stderr)
        return 2
    try:
        payload_raw = json.load(sys.stdin)
        if not isinstance(payload_raw, dict):
            raise RuntimeError("stdin 须为 JSON 对象")
        payload = SkillPayload(
            instruction=str(payload_raw.get("instruction") or ""),
            arguments={
                str(key): str(value)
                for key, value in dict(payload_raw.get("arguments") or {}).items()
            },
        )
        skill = _load_skill(Path(sys.argv[1]))
        result = skill.execute(payload)
        json.dump({"result": result}, sys.stdout, ensure_ascii=False, default=str)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:  # noqa: BLE001 — 子进程边界，统一 stderr
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
