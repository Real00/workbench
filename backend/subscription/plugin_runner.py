from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLUGIN_TIMEOUT_SECONDS = 30.0
MAX_STDOUT_BYTES = 8 * 1024 * 1024

_RUNTIME_ROOT = Path(__file__).resolve().parent
_BACKEND_ROOT = _RUNTIME_ROOT.parent
_ENTRY = _RUNTIME_ROOT / "plugin_runtime" / "entry.py"


@dataclass(frozen=True)
class PluginRunResult:
    articles: list[dict[str, Any]]
    stderr: str


class PluginSubprocessRunner:
    def __init__(
        self,
        *,
        timeout_seconds: float = PLUGIN_TIMEOUT_SECONDS,
        max_stdout_bytes: int = MAX_STDOUT_BYTES,
        python_executable: str | None = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_stdout_bytes = max_stdout_bytes
        self.python_executable = python_executable or sys.executable

    async def run(
        self,
        script: str,
        *,
        url: str,
        body: str,
        config: dict[str, Any] | None = None,
    ) -> PluginRunResult:
        payload = json.dumps(
            {"url": url, "body": body, "config": config or {}},
            ensure_ascii=False,
        ).encode("utf-8")
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(_BACKEND_ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        }
        with tempfile.TemporaryDirectory(prefix="sub-plugin-") as tmp:
            script_path = Path(tmp) / "plugin.py"
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
                limit=self.max_stdout_bytes + 1,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(payload),
                    timeout=self.timeout_seconds,
                )
            except TimeoutError as exc:
                process.kill()
                await process.wait()
                raise ValueError(f"插件执行超时（{self.timeout_seconds:.0f}s）") from exc
            err_text = stderr.decode("utf-8", errors="replace").strip()
            if process.returncode != 0:
                message = err_text.splitlines()[-1] if err_text else f"exit {process.returncode}"
                raise ValueError(f"插件执行失败: {message}")
            if len(stdout) > self.max_stdout_bytes:
                raise ValueError("插件输出过大")
            try:
                data = json.loads(stdout.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError("插件输出不是合法 JSON") from exc
            articles = data.get("articles") if isinstance(data, dict) else None
            if not isinstance(articles, list):
                raise ValueError("插件输出缺少 articles 数组")
            normalized: list[dict[str, Any]] = []
            for item in articles:
                if not isinstance(item, dict):
                    raise ValueError("articles 元素须为对象")
                normalized.append(item)
            return PluginRunResult(articles=normalized, stderr=err_text)
