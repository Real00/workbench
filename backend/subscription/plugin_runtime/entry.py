#!/usr/bin/env python3
"""子进程入口：加载用户脚本中的 SubscriptionParser 子类并执行 parse。

用法：python entry.py <script_path>
stdin: {"url": "...", "body": "...", "config": {}}
stdout: {"articles": [...]}
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import traceback
from pathlib import Path
from typing import Any

# 保证能 import subscription.plugin_runtime.base（由 runner 设置 PYTHONPATH）
from subscription.plugin_runtime.base import (  # noqa: E402
    ParsedArticle,
    ParsePayload,
    SubscriptionParser,
)


def _load_parser(script_path: Path) -> SubscriptionParser:
    spec = importlib.util.spec_from_file_location("user_subscription_plugin", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载插件脚本")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parsers: list[type[SubscriptionParser]] = []
    for value in vars(module).values():
        if (
            inspect.isclass(value)
            and issubclass(value, SubscriptionParser)
            and value is not SubscriptionParser
            and not inspect.isabstract(value)
        ):
            parsers.append(value)
    if not parsers:
        raise RuntimeError("脚本须定义 SubscriptionParser 子类")
    if len(parsers) > 1:
        raise RuntimeError("脚本只能定义一个 SubscriptionParser 子类")
    return parsers[0]()


def _normalize_articles(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise RuntimeError("parse() 须返回 list")
    articles: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, ParsedArticle):
            articles.append(item.to_dict())
        elif isinstance(item, dict):
            articles.append(ParsedArticle.from_mapping(item).to_dict())
        else:
            raise RuntimeError("文章须为 ParsedArticle 或 dict")
    return articles


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: entry.py <script_path>", file=sys.stderr)
        return 2
    try:
        payload_raw = json.load(sys.stdin)
        if not isinstance(payload_raw, dict):
            raise RuntimeError("stdin 须为 JSON 对象")
        payload = ParsePayload(
            url=str(payload_raw.get("url") or ""),
            body=str(payload_raw.get("body") or ""),
            config=dict(payload_raw.get("config") or {}),
        )
        parser = _load_parser(Path(sys.argv[1]))
        articles = _normalize_articles(parser.parse(payload))
        json.dump({"articles": articles}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:  # noqa: BLE001 — 子进程边界，统一 stderr
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
