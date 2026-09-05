import pytest

from progress.domain import Task
from progress.repository import task_document, task_from_document


def test_task_normalizes_tags_and_transitions() -> None:
    task = Task.create({"title": " Ship ", "tags": ["api", "api", ""]}, "admin")
    assert task.title == "Ship"
    assert task.tags == ["api"]

    task.change_status("cancelled")
    with pytest.raises(ValueError, match="cannot be reopened"):
        task.change_status("todo")


def test_task_rejects_invalid_priority() -> None:
    with pytest.raises(ValueError, match="invalid priority"):
        Task.create({"title": "Task", "priority": "impossible"}, "admin")


def test_task_validates_schedule_and_done_progress() -> None:
    with pytest.raises(ValueError, match="start_date"):
        Task.create(
            {"title": "Invalid", "start_date": "2026-09-10", "due_date": "2026-09-01"},
            "admin",
        )

    task = Task.create(
        {
            "title": "Gantt task",
            "start_date": "2026-09-01",
            "due_date": "2026-09-10",
            "estimated_hours": 12,
            "progress": 40,
        },
        "admin",
    )
    task.change_status("done")
    assert task.progress == 100
    assert task_from_document(task_document(task)).due_date == task.due_date


def test_task_records_progress_entries_without_splitting_tasks() -> None:
    task = Task.create({"title": "登录页"}, "admin")
    task.add_entry("blocker", "验证码服务超时")
    task.add_entry("extra_work", "先切到备用短信通道")
    restored = task_from_document(task_document(task))
    assert [entry.kind for entry in restored.entries] == ["blocker", "extra_work"]
    assert restored.entries[0].content == "验证码服务超时"

    snapshot = task.snapshot()
    snapshot.add_entry("update", "通道已恢复")
    assert len(task.entries) == 2
    assert len(snapshot.entries) == 3


def test_legacy_task_document_defaults_empty_entries() -> None:
    task = Task.create({"title": "Legacy"}, "admin")
    document = task_document(task)
    del document["entries"]
    del document["resources"]
    del document["project_id"]
    restored = task_from_document(document)
    assert restored.entries == []
    assert restored.resources == []
    assert restored.project_id is None


def test_task_accepts_images_documents_and_links() -> None:
    from progress.domain import TaskResource

    task = Task.create({"title": "登录页"}, "admin")
    resource, suffix = TaskResource.create_file("shot.png", 12)
    resource.storage_key = f"{task.id}/{resource.id}{suffix}"
    task.add_resource(resource)
    task.add_resource(TaskResource.create_link("规格", "https://example.test/spec"))
    restored = task_from_document(task_document(task))
    assert [item.kind for item in restored.resources] == ["image", "link"]
    removed = restored.remove_resource(resource.id)
    assert removed.kind == "image"
    assert len(restored.resources) == 1


def test_task_rejects_invalid_progress_and_hours() -> None:
    with pytest.raises(ValueError, match="progress"):
        Task.create({"title": "Invalid", "progress": 101}, "admin")
    with pytest.raises(ValueError, match="estimated_hours"):
        Task.create({"title": "Invalid", "estimated_hours": -1}, "admin")


def test_member_normalizes_skills_and_background() -> None:
    from progress.domain import TeamMember
    from progress.repository import member_from_document

    member = TeamMember.create(
        {
            "name": "Rui",
            "skills": [" Python ", "python", "", "工单对接"],
            "background": "  做过 IT 工单接口  ",
        }
    )
    assert member.skills == ["Python", "工单对接"]
    assert member.background == "做过 IT 工单接口"

    with pytest.raises(ValueError, match="too many skills"):
        member.update({"skills": [f"s{i}" for i in range(21)]})

    restored = member_from_document(
        {
            "id": "m1",
            "name": "Legacy",
            "title": "",
            "active": True,
            "color": None,
            "created_at": member.created_at,
            "updated_at": member.updated_at,
        }
    )
    assert restored.skills == []
    assert restored.background == ""


def test_project_validates_name_dates_and_members() -> None:
    from progress.domain import Project
    project = Project.create(
        {
            "name": "  MYAI 工单平台  ",
            "description": " 工单系统二期的联调与上线 ",
            "background": " 沿用现有审批流 ",
            "started_at": "2026-09-01",
            "member_ids": ["m1", " m2 ", "m1", ""],
        }
    )
    assert project.name == "MYAI 工单平台"
    assert project.description == "工单系统二期的联调与上线"
    assert str(project.started_at) == "2026-09-01"
    assert project.member_ids == ["m1", "m2"]

    with pytest.raises(ValueError, match="name is required"):
        project.update({"name": "   "})
    with pytest.raises(ValueError, match="invalid started_at"):
        project.update({"started_at": "09/01/2026"})
    with pytest.raises(ValueError, match="too many project members"):
        project.update({"member_ids": [f"m{i}" for i in range(51)]})
    assert project.status == "planning"
    project.update({"status": "active", "cover_color": "#36d9e9"})
    assert project.status == "active"
    assert project.cover_color == "#36d9e9"
    project.update({"cover_color": "#0f0"})
    assert project.cover_color == "#0f0"
    with pytest.raises(ValueError, match="invalid project status"):
        project.update({"status": "done"})
    with pytest.raises(ValueError, match="cover_color"):
        project.update({"cover_color": "蓝色渐变"})
    project.update({"cover_color": ""})
    assert project.cover_color is None
    project.update({"started_at": None, "member_ids": []})
    assert project.started_at is None
    assert project.member_ids == []


def test_project_document_converts_started_at_for_bson() -> None:
    from datetime import datetime

    from progress.domain import Project
    from progress.repository import project_document, project_from_document

    project = Project.create({"name": "MYAI", "started_at": "2026-09-05"})
    document = project_document(project)
    assert isinstance(document["started_at"], datetime)
    restored = project_from_document(document)
    assert str(restored.started_at) == "2026-09-05"

    no_date = project_document(Project.create({"name": "无日期"}))
    assert no_date["started_at"] is None


def test_member_evaluation_add_remove_and_roundtrip() -> None:
    from progress.domain import TeamMember
    from progress.repository import member_evaluation_from_data, member_from_document

    member = TeamMember.create({"name": "张三"})
    evaluation = member.add_evaluation("highlight", "  主动接管 MYAI 联调  ")
    assert evaluation.content == "主动接管 MYAI 联调"
    assert member.evaluations == [evaluation]

    with pytest.raises(ValueError, match="kind"):
        member.add_evaluation("bad", "内容")
    with pytest.raises(ValueError, match="required"):
        member.add_evaluation("note", "   ")

    restored = member_from_document(
        {
            "id": member.id,
            "name": member.name,
            "title": "",
            "active": True,
            "color": None,
            "skills": [],
            "background": "",
            "created_at": member.created_at,
            "updated_at": member.updated_at,
            "evaluations": [
                {"kind": "nonsense", "content": "旧评价", "created_at": evaluation.created_at}
            ],
        }
    )
    assert restored.evaluations[0].kind == "note"
    assert restored.evaluations[0].content == "旧评价"
    assert member_evaluation_from_data(restored.evaluations[0]) is restored.evaluations[0]

    removed = member.remove_evaluation(evaluation.id)
    assert removed.id == evaluation.id
    assert member.evaluations == []
    with pytest.raises(LookupError):
        member.remove_evaluation(evaluation.id)


def test_member_decodes_literal_unicode_escapes() -> None:
    from progress.domain import TeamMember, decode_unicode_text
    from progress.repository import member_from_document

    escaped = r"\u8d1f\u8d23 myai \u76f8\u5173\u7cfb\u7edf\u5f00\u53d1"
    assert decode_unicode_text(escaped) == "负责 myai 相关系统开发"

    member = TeamMember.create(
        {
            "name": r"\u5f20\u4e09",
            "skills": [r"\u540e\u7aef"],
            "background": escaped,
        }
    )
    assert member.name == "张三"
    assert member.skills == ["后端"]
    assert member.background == "负责 myai 相关系统开发"

    restored = member_from_document(
        {
            "id": "m2",
            "name": "Rui",
            "title": "",
            "active": True,
            "color": None,
            "skills": [r"\u5de5\u5355\u5bf9\u63a5"],
            "background": escaped,
            "created_at": member.created_at,
            "updated_at": member.updated_at,
        }
    )
    assert restored.skills == ["工单对接"]
    assert restored.background == "负责 myai 相关系统开发"
