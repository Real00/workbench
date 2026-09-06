from typing import Any

from aiohttp.helpers import AppKey, RequestKey
from pymongo import AsyncMongoClient

from ai_settings.application import AISettingsApplicationService
from identity.application import IdentityApplicationService
from knowledge.application import KnowledgeApplicationService
from progress.application import ProgressApplicationService
from pulse.application import PulseApplicationService
from shared.ai import ModuleAiContribution
from shared.config import Settings
from shared.events import ChangeEventBus
from shared.security import SecurityService

SETTINGS: AppKey[Settings] = AppKey("settings")
MONGO_CLIENT: AppKey[AsyncMongoClient[Any]] = AppKey("mongo_client")
SECURITY: AppKey[SecurityService] = AppKey("security")
IDENTITY: AppKey[IdentityApplicationService] = AppKey("identity")
PROGRESS: AppKey[ProgressApplicationService] = AppKey("progress")
KNOWLEDGE: AppKey[KnowledgeApplicationService] = AppKey("knowledge")
AI_SETTINGS: AppKey[AISettingsApplicationService] = AppKey("ai_settings")
AI_TASKS: AppKey[PulseApplicationService] = AppKey("ai_tasks")
AI_CONTRIBUTIONS: AppKey[list[ModuleAiContribution]] = AppKey("ai_contributions")
EVENT_BUS: AppKey[ChangeEventBus] = AppKey("event_bus")
ACTOR: RequestKey[dict[str, Any]] = RequestKey("actor")
CORS_ORIGIN: RequestKey[str | None] = RequestKey("cors_origin")
