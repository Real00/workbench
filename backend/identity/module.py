from aiohttp import web

from identity.application import IdentityApplicationService
from identity.domain import DeviceRepository, IdentityDomainService, UserRepository
from identity.repository import MongoDeviceRepository, MongoUserRepository
from identity.routes import register_routes
from shared.module import ModuleContext
from shared.web_keys import IDENTITY


class IdentityModule:
    def register(self, app: web.Application, context: ModuleContext) -> None:
        repository: UserRepository = context.overrides.get(
            "user_repository"
        ) or MongoUserRepository(context.mongo, context.settings.mongo_database)
        devices: DeviceRepository = context.overrides.get(
            "device_repository"
        ) or MongoDeviceRepository(context.mongo, context.settings.mongo_database)
        service = IdentityApplicationService(
            IdentityDomainService(repository), context.security, devices
        )
        app[IDENTITY] = service

        async def startup(_: web.Application) -> None:
            await service.initialize_admin(
                context.settings.admin_username, context.settings.admin_password
            )

        app.on_startup.append(startup)
        register_routes(app)
