from aiohttp import web

from shared.module import ModuleContext
from shared.web_keys import SYSTEM
from system.application import SystemApplicationService
from system.github import GithubCommitClient
from system.routes import register_routes


class SystemModule:
    def register(self, app: web.Application, context: ModuleContext) -> None:
        github = context.overrides.get("github_commits") or GithubCommitClient()
        control_store = context.overrides.get("update_control_store")
        service = SystemApplicationService(
            context.settings,
            github,
            control_store=control_store,
        )
        app[SYSTEM] = service
        register_routes(app)
