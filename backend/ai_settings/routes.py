from aiohttp import web
from pydantic import BaseModel

from ai_settings.agent_options import AgentOptionsInput, McpServerInput
from ai_settings.jev import JevInput
from ai_settings.skills import SkillInput
from api.http import body, response
from shared.ai import ModuleAiContribution, describe_contributions
from shared.web_keys import AI_CONTRIBUTIONS, AI_SETTINGS


class AISettingsInput(BaseModel):
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    jev: JevInput | None = None
    mcp_servers: list[McpServerInput] | None = None
    agent: AgentOptionsInput | None = None


class McpTestInput(BaseModel):
    url: str
    api_key: str | None = None
    headers: dict[str, str] | None = None


class SkillScriptTestInput(BaseModel):
    script: str
    instruction: str = "测试执行"


async def get_settings(request: web.Request) -> web.Response:
    return response(await request.app[AI_SETTINGS].get())


async def get_secret(request: web.Request) -> web.Response:
    return response(await request.app[AI_SETTINGS].get_secret())


async def put_settings(request: web.Request) -> web.Response:
    data = await body(request, AISettingsInput)
    return response(await request.app[AI_SETTINGS].configure(data))


async def test_connection(request: web.Request) -> web.Response:
    data = await request.json() if request.can_read_body else {}
    return response(await request.app[AI_SETTINGS].test_connection(data))


async def test_jev_connection(request: web.Request) -> web.Response:
    data = await body(request, JevInput)
    return response(await request.app[AI_SETTINGS].test_jev_connection(data))


async def test_mcp_connection(request: web.Request) -> web.Response:
    data = await body(request, McpTestInput)
    return response(await request.app[AI_SETTINGS].test_mcp_connection(data))


async def list_skills(request: web.Request) -> web.Response:
    return response(await request.app[AI_SETTINGS].list_skills())


async def create_skill(request: web.Request) -> web.Response:
    data = SkillInput.model_validate(await request.json())
    return response(await request.app[AI_SETTINGS].create_skill(data), status=201)


async def update_skill(request: web.Request) -> web.Response:
    data = SkillInput.model_validate(await request.json())
    skill = await request.app[AI_SETTINGS].update_skill(request.match_info["skill_id"], data)
    return response(skill)


async def delete_skill(request: web.Request) -> web.Response:
    return response(await request.app[AI_SETTINGS].delete_skill(request.match_info["skill_id"]))


async def test_skill_script(request: web.Request) -> web.Response:
    data = SkillScriptTestInput.model_validate(await request.json())
    result = await request.app[AI_SETTINGS].run_skill_script(data.script, data.instruction)
    return response(result)


async def get_tools(request: web.Request) -> web.Response:
    contributions: list[ModuleAiContribution] = request.app[AI_CONTRIBUTIONS]
    return response({"modules": describe_contributions(contributions)})


def register_routes(app: web.Application) -> None:
    app.router.add_get("/api/v1/ai-settings", get_settings)
    app.router.add_get("/api/v1/ai-settings/secret", get_secret)
    app.router.add_put("/api/v1/ai-settings", put_settings)
    app.router.add_post("/api/v1/ai-settings/test", test_connection)
    app.router.add_get("/api/v1/ai-settings/tools", get_tools)
    app.router.add_post("/api/v1/ai-settings/jev/test", test_jev_connection)
    app.router.add_post("/api/v1/ai-settings/mcp/test", test_mcp_connection)
    app.router.add_get("/api/v1/ai-settings/skills", list_skills)
    app.router.add_post("/api/v1/ai-settings/skills", create_skill)
    app.router.add_post("/api/v1/ai-settings/skills/test", test_skill_script)
    app.router.add_put("/api/v1/ai-settings/skills/{skill_id}", update_skill)
    app.router.add_delete("/api/v1/ai-settings/skills/{skill_id}", delete_skill)
