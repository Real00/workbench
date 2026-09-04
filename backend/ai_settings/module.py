from aiohttp import web

from ai_settings.application import AISettingsApplicationService
from ai_settings.domain import AISettingsDomainService, AISettingsRepository
from ai_settings.repository import MongoAISettingsRepository
from ai_settings.routes import register_routes
from shared.module import ModuleContext
from shared.web_keys import AI_SETTINGS


class AISettingsModule:
    def register(self, app: web.Application, context: ModuleContext) -> None:
        repository: AISettingsRepository = context.overrides.get(
            "ai_repository"
        ) or MongoAISettingsRepository(context.mongo, context.settings.mongo_database)
        service = AISettingsApplicationService(
            AISettingsDomainService(repository), context.security
        )
        app[AI_SETTINGS] = service
        context.services["ai_settings_reader"] = service

        async def startup(_: web.Application) -> None:
            await service.initialize()

        app.on_startup.append(startup)
        register_routes(app)
