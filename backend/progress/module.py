from aiohttp import web

from progress.ai_tools import progress_ai_contribution
from progress.application import ProgressApplicationService
from progress.domain import (
    MemberRepository,
    ProgressDomainService,
    ProjectRepository,
    TaskRepository,
)
from progress.repository import (
    MongoMemberRepository,
    MongoProjectRepository,
    MongoTaskRepository,
)
from progress.routes import register_routes
from progress.storage import FilesystemResourceStorage
from shared.module import ModuleContext
from shared.web_keys import IDENTITY, PROGRESS


class ProgressModule:
    def register(self, app: web.Application, context: ModuleContext) -> None:
        tasks: TaskRepository = context.overrides.get(
            "task_repository"
        ) or MongoTaskRepository(context.mongo, context.settings.mongo_database)
        members: MemberRepository = context.overrides.get(
            "member_repository"
        ) or MongoMemberRepository(context.mongo, context.settings.mongo_database)
        projects: ProjectRepository = context.overrides.get(
            "project_repository"
        ) or MongoProjectRepository(context.mongo, context.settings.mongo_database)
        domain = ProgressDomainService(tasks, members, projects)
        storage = context.overrides.get("resource_storage") or FilesystemResourceStorage(
            context.settings.upload_dir
        )
        service = ProgressApplicationService(domain, storage)
        app[PROGRESS] = service
        context.ai_contributions.append(progress_ai_contribution())

        async def startup(app: web.Application) -> None:
            admin = await app[IDENTITY].get_by_username(context.settings.admin_username)
            await service.initialize(operator=admin)

        app.on_startup.append(startup)
        register_routes(app)
