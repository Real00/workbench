from typing import cast

from aiohttp import web

from ai_settings.ports import AISettingsReader
from pulse.application import PulseApplicationService
from pulse.routes import register_routes
from shared.module import ModuleContext
from shared.web_keys import AI_TASKS, KNOWLEDGE, PROGRESS


class PulseModule:
    def register(self, app: web.Application, context: ModuleContext) -> None:
        settings_reader = cast(AISettingsReader, context.services["ai_settings_reader"])
        app[AI_TASKS] = PulseApplicationService(
            settings_reader,
            app[PROGRESS].domain,
            context.security,
            context.settings.preview_ttl_seconds,
            agent=context.overrides.get("progress_agent") or context.overrides.get("pulse_agent"),
            knowledge=app[KNOWLEDGE],
            contributions=context.ai_contributions,
        )
        register_routes(app)
