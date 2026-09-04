import asyncio

from aiohttp import web
from pydantic import BaseModel, Field
from pydantic_ai import CancellationToken

from api.http import body, dumps, response
from shared.web_keys import ACTOR, AI_TASKS


class AIPreviewInput(BaseModel):
    instruction: str = Field(min_length=1, max_length=4000)
    context_task_id: str | None = None
    context_document_id: str | None = None
    session_id: str | None = Field(default=None, max_length=64)


class AIConfirmInput(BaseModel):
    confirmation_token: str


async def run_ai_task(request: web.Request) -> web.StreamResponse:
    data = await body(request, AIPreviewInput)
    stream = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    await stream.prepare(request)
    try:
        await stream.write(b": connected\n\n")
    except (ConnectionResetError, ConnectionAbortedError, OSError):
        return stream
    cancel = CancellationToken()
    watcher = asyncio.create_task(_cancel_on_disconnect(request, cancel))
    try:
        async for event in request.app[AI_TASKS].stream(
            data["instruction"],
            data.get("context_task_id"),
            cancel,
            context_document_id=data.get("context_document_id"),
            session_id=data.get("session_id"),
        ):
            try:
                await stream.write(f"data: {dumps(event)}\n\n".encode())
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                cancel.cancel()
                break
    except Exception as extra:
        if not cancel.cancelled:
            payload = dumps({"type": "error", "message": str(extra)})
            try:
                await stream.write(f"data: {payload}\n\n".encode())
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                cancel.cancel()
    finally:
        cancel.cancel()
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
        try:
            await stream.write_eof()
        except (ConnectionResetError, ConnectionAbortedError, OSError):
            pass
    return stream


async def _cancel_on_disconnect(request: web.Request, cancel: CancellationToken) -> None:
    saw_transport = False
    try:
        while not cancel.cancelled:
            transport = request.transport
            if transport is not None:
                saw_transport = True
                if transport.is_closing():
                    cancel.cancel()
                    return
            elif saw_transport:
                cancel.cancel()
                return
            await asyncio.sleep(0.25)
    except asyncio.CancelledError:
        return


async def confirm_ai_task(request: web.Request) -> web.Response:
    data = await body(request, AIConfirmInput)
    return response(
        await request.app[AI_TASKS].confirm(data["confirmation_token"], request[ACTOR]["sub"])
    )


def register_routes(app: web.Application) -> None:
    app.router.add_post("/api/v1/ai/run", run_ai_task)
    app.router.add_post("/api/v1/ai/confirm", confirm_ai_task)
