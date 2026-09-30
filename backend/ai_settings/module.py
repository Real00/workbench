from aiohttp import web

from ai_settings.application import AISettingsApplicationService
from ai_settings.domain import AISettingsDomainService, AISettingsRepository
from ai_settings.repository import MongoAISettingsRepository
from ai_settings.routes import register_routes
from ai_settings.skill_runner import SkillScriptRunner
from ai_settings.skills_repository import MongoSkillRepository
from shared.module import ModuleContext
from shared.web_keys import AI_SETTINGS


class AISettingsModule:
    def register(self, app: web.Application, context: ModuleContext) -> None:
        repository: AISettingsRepository = context.overrides.get(
            "ai_repository"
        ) or MongoAISettingsRepository(context.mongo, context.settings.mongo_database)
        skills_repository = context.overrides.get("ai_skills_repository") or MongoSkillRepository(
            context.mongo, context.settings.mongo_database
        )
        skill_runner = context.overrides.get("ai_skill_runner") or SkillScriptRunner()
        service = AISettingsApplicationService(
            AISettingsDomainService(repository), context.security,
            skills_repository=skills_repository, skill_runner=skill_runner,
        )
        app[AI_SETTINGS] = service
        context.services["ai_settings_reader"] = service

        async def startup(_: web.Application) -> None:
            await service.initialize()

        app.on_startup.append(startup)
        register_routes(app)
