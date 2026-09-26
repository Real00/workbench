"""Best-effort tool preloading; unselected tools remain discoverable via ToolSearch."""

import logging
from collections.abc import Sequence
from hashlib import sha256
from time import monotonic
from typing import Any

from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from ai_settings.jev import JevConnectionSettings
from shared.ai import ModuleAiContribution, describe_tool
from shared.jev import JevTimeoutError, evaluate_tools

logger = logging.getLogger(__name__)
MAX_PRELOADED_TOOLS = 5
MAX_ROUTING_TEXT = 12000
TIMEOUT_FAILURE_LIMIT = 3
CIRCUIT_COOLDOWN_SECONDS = 60


class JevCircuitBreaker:
    """Per-agent circuit shared by conversations within one backend process.

    State transitions contain no awaits. Generation tickets prevent late results
    from an earlier configuration or closed circuit from undoing a newer trip.
    """

    def __init__(self) -> None:
        self.key: tuple[str, str, str, float] | None = None
        self.generation = 0
        self.timeouts = 0
        self.open_until = 0.0
        self.probing = False

    def reset(self) -> None:
        self.key = None
        self.generation += 1
        self.timeouts = 0
        self.open_until = 0.0
        self.probing = False

    def acquire(self, settings: JevConnectionSettings) -> int | None:
        key = (
            settings.base_url,
            settings.model,
            sha256(settings.api_key.encode()).hexdigest(),
            settings.timeout_seconds,
        )
        if key != self.key:
            self.reset()
            self.key = key
        if self.probing:
            return None
        if self.open_until:
            if monotonic() < self.open_until:
                return None
            self.probing = True
        return self.generation

    def finish(self, ticket: int, outcome: str) -> None:
        if ticket != self.generation:
            return
        was_probe = self.probing
        self.probing = False
        if outcome == "cancelled":
            return
        if outcome == "success":
            self.timeouts = 0
            self.open_until = 0.0
            return
        self.timeouts = self.timeouts + 1 if outcome == "timeout" else 0
        if was_probe or self.timeouts >= TIMEOUT_FAILURE_LIMIT:
            self.open_until = monotonic() + CIRCUIT_COOLDOWN_SECONDS
            self.generation += 1
            logger.warning("Jev circuit open; using default ToolSearch for 60s")


def routing_state(prompt: str, history: Sequence[Any] | None) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    for message in list(history or [])[-8:]:
        for part in getattr(message, "parts", []):
            if isinstance(message, ModelRequest) and isinstance(part, UserPromptPart):
                if isinstance(part.content, str):
                    messages.append({"role": "user", "text": part.content[-2000:]})
            elif isinstance(message, ModelResponse) and isinstance(part, TextPart):
                messages.append({"role": "assistant", "text": part.content[-2000:]})
    return {"request": prompt, "recent_messages": messages[-6:]}


async def preload_tools(
    settings: JevConnectionSettings | None,
    contributions: Sequence[ModuleAiContribution],
    always_available: set[str],
    prompt: str,
    history: Sequence[Any] | None,
    *,
    breaker: JevCircuitBreaker | None = None,
) -> set[str]:
    # Skip very large requests instead of classifying a truncated user intent.
    if settings is None:
        if breaker:
            breaker.reset()
        return set()
    if len(prompt) > MAX_ROUTING_TEXT:
        return set()
    candidates = {
        fn.__name__: describe_tool(fn)["description"]
        for item in contributions
        for fn in item.tools
        if fn.__name__ not in always_available
    }
    if not candidates:
        return set()
    ticket = breaker.acquire(settings) if breaker else 0
    if ticket is None:
        return set()
    outcome = "cancelled"
    try:
        probabilities = await evaluate_tools(settings, routing_state(prompt, history), candidates)
        outcome = "success"
    except JevTimeoutError:
        outcome = "timeout"
        logger.info("Jev timed out; retaining ToolSearch discovery")
        return set()
    except ValueError:
        outcome = "error"
        logger.info("Jev preloading unavailable; retaining ToolSearch discovery")
        return set()
    finally:
        if breaker:
            breaker.finish(ticket, outcome)
    ranked = sorted(probabilities, key=lambda name: probabilities[name], reverse=True)
    return {
        name for name in ranked[:MAX_PRELOADED_TOOLS] if probabilities[name] >= settings.threshold
    }
