from dataclasses import dataclass, field
from typing import Any, Protocol

from aiohttp import web
from pymongo import AsyncMongoClient

from shared.ai import ModuleAiContribution
from shared.config import Settings
from shared.security import SecurityService


@dataclass
class ModuleContext:
    settings: Settings
    mongo: AsyncMongoClient[Any]
    security: SecurityService
    overrides: dict[str, Any]
    services: dict[str, Any] = field(default_factory=dict)
    ai_contributions: list[ModuleAiContribution] = field(default_factory=list)


class AppModule(Protocol):
    def register(self, app: web.Application, context: ModuleContext) -> None: ...
