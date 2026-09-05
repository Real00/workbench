from uuid import UUID

from aiohttp import web
from pydantic import BaseModel, ConfigDict, Field

from api.http import body, response
from capture.application import CaptureApplicationService
from capture.repository import MongoCaptureRepository
from shared.module import ModuleContext
from shared.web_keys import ACTOR


class CaptureInput(BaseModel):
    id: UUID
    content: str = Field(min_length=1, max_length=20000)


class CaptureUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pinned: bool = False
    archived: bool = False


class CaptureModule:
    def register(self, app: web.Application, context: ModuleContext) -> None:
        repository = context.overrides.get("capture_repository") or MongoCaptureRepository(
            context.mongo, context.settings.mongo_database
        )
        service = CaptureApplicationService(repository)

        async def create(request: web.Request) -> web.Response:
            data = await body(request, CaptureInput)
            return response(await service.create(
                request[ACTOR]["sub"], str(data["id"]), data["content"]
            ), 201)

        async def listing(request: web.Request) -> web.Response:
            offset = int(request.query.get("offset", "0"))
            if offset < 0:
                raise ValueError("invalid offset")
            return response(await service.list(
                request[ACTOR]["sub"], request.query.get("q", "")[:200],
                request.query.get("archived") == "true", offset,
            ))

        async def update(request: web.Request) -> web.Response:
            return response(await service.update(
                request[ACTOR]["sub"], request.match_info["id"],
                await body(request, CaptureUpdate),
            ))

        app.router.add_get("/api/v1/captures", listing)
        app.router.add_post("/api/v1/captures", create)
        app.router.add_patch("/api/v1/captures/{id}", update)
