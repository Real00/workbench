from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry

from knowledge.ai_tools import create_entry, list_tags, search_knowledge
from knowledge.application import KnowledgeApplicationService
from knowledge.corpus import MemoryKnowledgeCorpus
from knowledge.domain import KnowledgeDomainService
from knowledge.extract import extract_markdown
from progress.domain import ProgressDomainService
from pulse.deps import AgentDeps
from tests.fakes import (
    MemoryDocumentRepository,
    MemoryEntryRepository,
    MemoryMemberRepository,
    MemoryProjectRepository,
    MemoryTagRepository,
    MemoryTaskRepository,
)


def _service() -> KnowledgeApplicationService:
    return KnowledgeApplicationService(
        KnowledgeDomainService(
            MemoryTagRepository(), MemoryEntryRepository(), MemoryDocumentRepository()
        ),
        MemoryKnowledgeCorpus(),
    )


async def test_tag_requires_explanation_and_unique_name() -> None:
    service = _service()
    tag = await service.create_tag({"name": "架构", "explanation": "系统分层约定"})
    assert tag["explanation"] == "系统分层约定"
    with pytest.raises(ValueError, match="already exists"):
        await service.create_tag({"name": "架构", "explanation": "重复"})
    with pytest.raises(ValueError, match="explanation"):
        await service.create_tag({"name": "空", "explanation": "  "})


async def test_entry_key_is_unique() -> None:
    service = _service()
    await service.create_entry({"key": "Pulse", "value": "工作台 AI 对话框"})
    with pytest.raises(ValueError, match="already exists"):
        await service.create_entry({"key": "Pulse", "value": "重复"})


async def test_reimport_without_apply_keeps_edited_body() -> None:
    service = _service()
    document = await service.create_document({"title": "约定", "body": "手改过的正文"})
    await service.import_document(
        document["id"], "notes.md", "# extracted\n\n抽出的新正文".encode(), apply_body=False
    )
    refreshed = await service.get_document(document["id"])
    assert refreshed["body"] == "手改过的正文"
    assert refreshed["has_raw"] is True
    assert "抽出的新正文" not in service.corpus.read(f"wiki/documents/{document['id']}.md")


async def test_create_document_from_file_sets_body_and_raw() -> None:
    service = _service()
    document = await service.create_document_from_file(
        "会议纪要.md", "# 纪要\n\n讨论检索".encode(), {"title": "会议纪要"}
    )
    assert document["title"] == "会议纪要"
    assert "讨论检索" in document["body"]
    assert document["has_raw"] is True
    assert document["raw_filename"] == "会议纪要.md"
    with pytest.raises(ValueError, match="unsupported"):
        await service.create_document_from_file("slides.pdf", b"%PDF", {"title": "幻灯片"})


async def test_entry_links_to_document_both_sides() -> None:
    service = _service()
    tag = await service.create_tag({"name": "平台", "explanation": "工作台本身"})
    document = await service.create_document({"title": "Pulse", "body": "平台助手"})
    entry = await service.create_entry(
        {
            "key": "Pulse",
            "value": "工作台 AI 对话框",
            "tag_ids": [tag["id"]],
            "document_ids": [document["id"]],
            "aliases": ["助手"],
        }
    )
    assert entry["document_ids"] == [document["id"]]
    refreshed = await service.get_document(document["id"])
    assert refreshed["entry_ids"] == [entry["id"]]
    await service.delete_entry(entry["id"])
    assert (await service.get_document(document["id"]))["entry_ids"] == []


async def test_compile_then_grep_hits_body_not_raw() -> None:
    service = _service()
    document = await service.create_document(
        {"title": "登录约定", "body": "验证码超时先切备用通道"}
    )
    await service.import_document(
        document["id"], "notes.md", "new body that mentions 工单".encode()
    )
    hits = service.corpus.search("工单", glob="wiki/documents/**")
    assert hits
    assert all(not item["path"].startswith("raw/") for item in hits)
    with pytest.raises(LookupError, match="raw"):
        service.corpus.read(f"raw/documents/{document['id']}/notes.md")
        files = service.corpus.search(
            "登录约定", glob="wiki/documents/**", output_mode="files_with_matches"
        )
        assert files == [f"wiki/documents/{document['id']}.md"]
    renamed = await service.update_document(document["id"], {"title": "新标题"})
    assert service.corpus.read(f"wiki/documents/{renamed['id']}.md").startswith("---")
    assert "新标题" in service.corpus.read("index.md")


async def test_extract_markdown_and_reject_pdf() -> None:
    body = extract_markdown("note.md", "# 标题\n\n一段说明".encode())
    assert "一段说明" in body
    with pytest.raises(ValueError, match="unsupported"):
        extract_markdown("file.pdf", b"%PDF")


async def test_create_entry_tool_queues_and_confirm_writes_corpus() -> None:
    from ai_settings.application import AISettingsApplicationService
    from ai_settings.domain import AISettingsDomainService
    from progress.ai_application import AITaskApplicationService
    from shared.security import SecurityService
    from tests.fakes import MemoryAISettingsRepository
    from tests.test_ai import FakeProgressAgent

    knowledge = _service()
    progress = ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository())
    security = SecurityService("test-secret-with-at-least-32-characters", 60)
    ai_domain = AISettingsDomainService(MemoryAISettingsRepository())
    await ai_domain.configure(
        "https://example.test/v1", "test-model", security.encrypt("secret-api-key")
    )
    ctx = SimpleNamespace(
        deps=AgentDeps(progress=progress, knowledge=knowledge.domain, corpus=knowledge.corpus)
    )
    queued = await create_entry(ctx, key="负责人", value="可分配给管理员")
    assert queued["queued"] is True
    assert await knowledge.list_entries() == []
    agent = FakeProgressAgent([{"type": "text", "delta": "将创建条目"}], ctx.deps.pending)
    service = AITaskApplicationService(
        AISettingsApplicationService(ai_domain, security),
        progress,
        security,
        60,
        agent=agent,
        knowledge=knowledge,
    )
    events = [event async for event in service.stream("记下负责人")]
    confirmed = await service.confirm(events[-1]["confirmation_token"], "admin")
    assert confirmed[0]["key"] == "负责人"
    assert "负责人" in knowledge.corpus.read("index.md")


async def test_attachment_is_quoted_in_prompt_and_saved_as_document_on_confirm() -> None:
    from ai_settings.application import AISettingsApplicationService
    from ai_settings.domain import AISettingsDomainService
    from knowledge.ai_tools import save_attachment_as_document
    from progress.ai_application import AITaskApplicationService
    from pulse.ai_tools import read_attachment
    from shared.security import SecurityService
    from tests.fakes import MemoryAISettingsRepository
    from tests.test_ai import FakeProgressAgent

    knowledge = _service()
    progress = ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository())
    security = SecurityService("test-secret-with-at-least-32-characters", 60)
    ai_domain = AISettingsDomainService(MemoryAISettingsRepository())
    await ai_domain.configure(
        "https://example.test/v1", "test-model", security.encrypt("secret-api-key")
    )
    agent = FakeProgressAgent([{"type": "text", "delta": "将导入附件"}])
    service = AITaskApplicationService(
        AISettingsApplicationService(ai_domain, security),
        progress,
        security,
        60,
        agent=agent,
        knowledge=knowledge,
    )
    with pytest.raises(ValueError, match="暂不支持"):
        service.add_attachment("slides.pdf", b"%PDF")
    meta = service.add_attachment("会议纪要.md", "# 纪要\n\n验证码超时先切备用通道".encode())
    assert meta["name"] == "会议纪要.md" and meta["chars"] > 0

    expired = [event async for event in service.stream("看看附件", attachment_ids=["missing"])]
    assert expired == [{"type": "error", "message": "附件已过期或不存在，请重新粘贴文件"}]

    events = [event async for event in service.stream("把附件存进知识库", attachment_ids=[meta["id"]])]
    assert events[-1]["type"] == "done"
    prompt = agent.prompts[-1]
    assert f'<attachment id="{meta["id"]}" name="会议纪要.md"' in prompt
    assert "验证码超时先切备用通道" in prompt
    assert "save_attachment_as_document" in prompt

    attachment = service.attachments.get(meta["id"])
    assert attachment is not None
    ctx = SimpleNamespace(
        deps=AgentDeps(
            progress=progress,
            knowledge=knowledge.domain,
            corpus=knowledge.corpus,
            attachments=[attachment],
        )
    )
    piece = await read_attachment(ctx, meta["id"], offset=0, limit=4)
    assert piece["text"] == "# 纪要" and piece["has_more"] is True
    with pytest.raises(ModelRetry, match="unknown attachment_id"):
        await save_attachment_as_document(ctx, attachment_id="nope", title="x")
    queued = await save_attachment_as_document(ctx, attachment_id=meta["id"], title="登录纪要")
    assert queued["queued"] is True
    assert ctx.deps.pending[0]["op"] == "create_document_from_attachment"
    assert "body" not in ctx.deps.pending[0]["changes"]
    assert await knowledge.list_documents() == []

    agent.pending = ctx.deps.pending
    done = [event async for event in service.stream("确认", attachment_ids=[meta["id"]])][-1]
    confirmed = await service.confirm(done["confirmation_token"], "admin")
    assert confirmed[0]["title"] == "登录纪要"
    assert confirmed[0]["has_raw"] is True
    assert "验证码超时先切备用通道" in confirmed[0]["body"]
    assert knowledge.corpus.search("备用通道", glob="wiki/documents/**")


async def test_list_tags_tool_includes_explanation() -> None:
    knowledge = _service()
    await knowledge.create_tag({"name": "平台", "explanation": "工作台本身"})
    progress = ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository())
    ctx = SimpleNamespace(
        deps=AgentDeps(progress=progress, knowledge=knowledge.domain, corpus=knowledge.corpus)
    )
    tags = await list_tags(ctx)
    assert tags == [{"id": tags[0]["id"], "name": "平台", "explanation": "工作台本身"}]


async def test_search_knowledge_tool_skips_raw() -> None:
    knowledge = _service()
    await knowledge.create_document({"title": "规范", "body": "工单对接走内部网关"})
    progress = ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository())
    ctx = SimpleNamespace(
        deps=AgentDeps(progress=progress, knowledge=knowledge.domain, corpus=knowledge.corpus)
    )
    hits = await search_knowledge(ctx, "工单对接", glob="wiki/**")
    assert hits[0]["text"].find("工单对接") >= 0
    with pytest.raises(ModelRetry, match="raw"):
        await search_knowledge(ctx, "x", glob="raw/**")


async def test_knowledge_http_create_document_and_entry() -> None:
    from aiohttp import FormData
    from aiohttp.test_utils import TestClient, TestServer

    from app import create_app
    from shared.config import Settings
    from tests.fakes import (
        MemoryAISettingsRepository,
        MemoryMemberRepository,
        MemoryResourceStorage,
        MemorySkillsRepository,
        MemoryTaskRepository,
        MemoryUserRepository,
        knowledge_overrides,
    )

    app = create_app(
        Settings(admin_password="password123"),
        user_repository=MemoryUserRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        ai_repository=MemoryAISettingsRepository(),
        ai_skills_repository=MemorySkillsRepository(),
        resource_storage=MemoryResourceStorage(),
        **knowledge_overrides(),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "password123"}
        )
        headers = {"Authorization": f"Bearer {(await login.json())['access_token']}"}
        tag = await client.post(
            "/api/v1/knowledge/tags",
            json={"name": "平台", "explanation": "工作台约定"},
            headers=headers,
        )
        assert tag.status == 201
        tag_id = (await tag.json())["id"]
        document = await client.post(
            "/api/v1/knowledge/documents",
            json={"title": "检索", "body": "明文 Markdown 按行 grep"},
            headers=headers,
        )
        assert document.status == 201
        doc = await document.json()
        entry = await client.post(
            "/api/v1/knowledge/entries",
            json={
                "key": "grep",
                "value": "按行匹配明文",
                "tag_ids": [tag_id],
                "document_ids": [doc["id"]],
            },
            headers=headers,
        )
        assert entry.status == 201
        listed = await client.get("/api/v1/knowledge/documents", headers=headers)
        body = await listed.json()
        assert body[0]["entry_ids"] == [(await entry.json())["id"]]
        moved = await client.patch(
            f"/api/v1/knowledge/documents/{doc['id']}/canvas",
            json={"canvas_x": 120, "canvas_y": 80},
            headers=headers,
        )
        assert (await moved.json())["canvas_x"] == 120
        upload = FormData()
        upload.add_field(
            "file",
            "# 抽出\n\n按行可搜".encode(),
            filename="note.md",
            content_type="text/markdown",
        )
        extracted = await client.post(
            "/api/v1/knowledge/extract", data=upload, headers=headers
        )
        assert extracted.status == 200
        assert "按行可搜" in (await extracted.json())["body"]
        from_file = FormData()
        from_file.add_field(
            "file",
            "# 上传建档\n\n正文进 wiki".encode(),
            filename="上传建档.md",
            content_type="text/markdown",
        )
        created = await client.post(
            "/api/v1/knowledge/documents/from-file", data=from_file, headers=headers
        )
        assert created.status == 201
        created_doc = await created.json()
        assert created_doc["title"] == "上传建档"
        assert "正文进 wiki" in created_doc["body"]
        assert created_doc["has_raw"] is True
        bad = FormData()
        bad.add_field("file", b"%PDF", filename="slides.pdf", content_type="application/pdf")
        rejected = await client.post(
            "/api/v1/knowledge/documents/from-file", data=bad, headers=headers
        )
        assert rejected.status == 400
    finally:
        await client.close()
