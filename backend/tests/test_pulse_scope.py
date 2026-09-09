from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry

from knowledge.ai_tools import list_entries, list_tags, read_knowledge, search_knowledge
from progress.ai_tools import create_task, get_task, list_tasks, update_task
from pulse.deps import AgentDeps
from pulse.scope import ProjectScope, mentions, resolve_scope
from tests.test_ai import build_service
from tests.test_knowledge import _service


async def test_scoped_retrieval_filters_before_limit_and_blocks_direct_reads():
    _, progress, _, _ = await build_service()
    knowledge = _service()
    mine = await knowledge.create_tag({"name": "myai", "explanation": "工单项目"})
    other = await knowledge.create_tag({"name": "agentstudio", "explanation": "智能体项目"})
    own_doc = await knowledge.create_document(
        {"title": "权限", "body": "权限采用角色授权", "tag_ids": [mine["id"]]}
    )
    foreign = await knowledge.create_document(
        {"title": "agentstudio 权限", "body": "权限与 myai 对接", "tag_ids": [other["id"]]}
    )
    await knowledge.create_entry(
        {
            "key": "agentstudio",
            "value": "不应出现",
            "tag_ids": [other["id"]],
            "document_ids": [own_doc["id"]],
        }
    )
    own_entry = await knowledge.create_entry(
        {"key": "myai 权限", "value": "仅按需读取完整内容", "tag_ids": [mine["id"]]}
    )
    ctx = SimpleNamespace(
        deps=AgentDeps(
            progress=progress,
            knowledge=knowledge.domain,
            corpus=knowledge.corpus,
            scopes=[ProjectScope("myai", terms=("myai",))],
        )
    )
    files = await search_knowledge(ctx, "权限", "wiki/documents/**", "files_with_matches", 1)
    assert files == [f"wiki/documents/{own_doc['id']}.md"]
    assert "agentstudio" not in await read_knowledge(ctx, "index.md")
    assert "agentstudio" not in await read_knowledge(ctx, files[0])
    with pytest.raises(ModelRetry, match="outside"):
        await read_knowledge(ctx, f"wiki/documents/{foreign['id']}.md")
    assert [tag["name"] for tag in await list_tags(ctx)] == ["myai"]
    entries = await list_entries(ctx)
    assert [entry["id"] for entry in entries] == [own_entry["id"]]
    assert "value" not in entries[0]
    assert await search_knowledge(ctx, "与 myai 对接") == []


async def test_switching_project_discards_history_but_followup_preserves_it():
    service, progress, agent, _ = await build_service()
    await progress.create_project({"name": "myai 工单平台"})
    await progress.create_project({"name": "agentstudio"})
    first = [event async for event in service.stream("创建 agentstudio 任务")]
    session_id = first[-1]["session_id"]
    second = [event async for event in service.stream("创建 myai 任务", session_id=session_id)]
    assert second[-1]["type"] == "done"
    assert agent.histories[-1] == []
    assert "Current explicit scope: myai" in agent.prompts[-1]
    _ = [event async for event in service.stream("继续", session_id=session_id)]
    assert len(agent.histories[-1]) == 2
    assert "Current explicit scope: myai" in agent.prompts[-1]


async def test_task_scope_rejects_foreign_project_and_tags_and_preserves_ownership():
    service, progress, _, _ = await build_service()
    mine = await progress.create_project({"name": "myai"})
    other = await progress.create_project({"name": "agentstudio 平台"})
    foreign = await progress.create({"title": "权限", "project_id": other.id}, "admin")
    ctx = SimpleNamespace(
        deps=AgentDeps(
            progress=progress,
            scopes=[ProjectScope("myai", mine.id, ("myai",))],
            instruction="创建权限任务，标签权限",
        )
    )
    await create_task(ctx, title="权限", tags=["myai", "权限"])
    changes = ctx.deps.pending[0]["changes"]
    assert changes["project_id"] == mine.id
    token = service.security.issue_preview_token(
        {"operations": ctx.deps.pending}, 60, purpose="progress-ai-preview"
    )
    saved = await service.confirm(token, "admin")
    assert saved[0]["project_id"] == mine.id
    assert [item["project_id"] for item in await list_tasks(ctx)] == [mine.id]
    for kwargs in ({"project_id": other.id}, {"tags": ["agentstudio"]}):
        with pytest.raises(ModelRetry):
            await create_task(ctx, title="错误归属", **kwargs)
    with pytest.raises(ModelRetry, match="outside"):
        await get_task(ctx, task_id=foreign.id)
    with pytest.raises(ModelRetry, match="outside"):
        await update_task(ctx, task_id=foreign.id, status="done")
    assert len(ctx.deps.pending) == 1


async def test_tag_only_scope_does_not_allow_copying_foreign_source_tags():
    _, progress, _, _ = await build_service()
    knowledge = _service()
    for name in ("myai", "agentstudio"):
        await knowledge.create_tag({"name": name, "explanation": name})
    scopes = await resolve_scope(progress, knowledge.domain, "创建 myai 任务", [])
    ctx = SimpleNamespace(
        deps=AgentDeps(
            progress=progress,
            knowledge=knowledge.domain,
            scopes=scopes,
            instruction="创建 myai 任务",
        )
    )
    with pytest.raises(ModelRetry, match="task tags"):
        await create_task(ctx, title="权限", tags=["agentstudio"])
    assert ctx.deps.pending == []
    await create_task(ctx, title="权限", tags=["myai"])
    assert ctx.deps.pending[0]["changes"]["tags"] == ["myai"]


async def test_explicit_mentions_and_cross_project_requests_resolve_scope():
    _, progress, _, _ = await build_service()
    mine = await progress.create_project({"name": "myai"})
    other = await progress.create_project({"name": "agentstudio"})
    scopes = await resolve_scope(progress, None, "比较 myai 和 agentstudio", [])
    assert {scope.project_id for scope in scopes} == {mine.id, other.id}
    scopes = await resolve_scope(progress, None, "创建任务", [{"type": "project", "id": mine.id}])
    assert [scope.project_id for scope in scopes] == [mine.id]
    assert mentions("创建MYAI任务", "myai")
    assert not mentions("myai-server", "myai")
