"""技能脚本沙箱：与订阅插件相同的白名单子进程模型（env 白名单 + 超时 + 输出上限）。"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

SKILL_TIMEOUT_SECONDS = 30.0
MAX_SKILL_OUTPUT_BYTES = 128 * 1024

_RUNTIME_ROOT = Path(__file__).resolve().parent
_ENTRY = _RUNTIME_ROOT / "skill_runtime" / "entry.py"


class SkillScriptRunner:
    def __init__(
        self,
        *,
        timeout_seconds: float = SKILL_TIMEOUT_SECONDS,
        max_output_bytes: int = MAX_SKILL_OUTPUT_BYTES,
        python_executable: str | None = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.python_executable = python_executable or sys.executable

    async def run(
        self, script: str, *, instruction: str, arguments: dict[str, str] | None = None
    ) -> Any:
        payload = json.dumps(
            {"instruction": instruction, "arguments": arguments or {}},
            ensure_ascii=False,
        ).encode("utf-8")
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(_RUNTIME_ROOT.parent),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        }
        with tempfile.TemporaryDirectory(prefix="pulse-skill-") as tmp:
            script_path = Path(tmp) / "skill.py"
            script_path.write_text(script, encoding="utf-8")
            process = await asyncio.create_subprocess_exec(
                self.python_executable,
                str(_ENTRY),
                str(script_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tmp,
                env=env,
                limit=self.max_output_bytes + 1,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(payload),
                    timeout=self.timeout_seconds,
                )
            except TimeoutError as exc:
                process.kill()
                await process.wait()
                raise ValueError(f"技能执行超时（{self.timeout_seconds:.0f}s）") from exc
            err_text = stderr.decode("utf-8", errors="replace").strip()
            if process.returncode != 0:
                message = err_text.splitlines()[-1] if err_text else f"exit {process.returncode}"
                raise ValueError(f"技能执行失败: {message}")
            if len(stdout) > self.max_output_bytes:
                raise ValueError("技能输出过大")
            try:
                data = json.loads(stdout.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError("技能输出不是合法 JSON") from exc
            if not isinstance(data, dict) or "result" not in data:
                raise ValueError("技能输出缺少 result 字段")
            return data["result"]
