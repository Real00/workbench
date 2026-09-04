from identity.application import IdentityApplicationService
from identity.domain import IdentityDomainService
from progress.application import ProgressApplicationService
from progress.domain import ProgressDomainService
from shared.security import SecurityService
from tests.fakes import (
    MemoryMemberRepository,
    MemoryProjectRepository,
    MemoryResourceStorage,
    MemoryTaskRepository,
    MemoryUserRepository,
)


async def test_identity_initializes_one_admin_and_authenticates() -> None:
    repository = MemoryUserRepository()
    security = SecurityService("test-secret-with-at-least-32-characters", 60)
    service = IdentityApplicationService(IdentityDomainService(repository), security)
    await service.initialize_admin("admin", "password123")
    await service.initialize_admin("other", "password123")

    assert await repository.count() == 1
    result = await service.login("admin", "password123")
    assert result["user"]["role"] == "admin"
    assert security.decode_token(result["access_token"])["role"] == "admin"


async def test_progress_dashboard_and_filtering() -> None:
    repository = MemoryTaskRepository()
    members = MemoryMemberRepository()
    service = ProgressApplicationService(
        ProgressDomainService(repository, members, MemoryProjectRepository()), MemoryResourceStorage()
    )
    member = await service.create_member({"name": "Rui", "title": "Engineer", "color": "#3366ff"})
    await service.create_task(
        {
            "title": "One",
            "priority": "high",
            "assignee_id": member["id"],
            "progress": 50,
            "estimated_hours": 16,
        },
        "actor",
    )
    await service.create_task({"title": "Two", "status": "done"}, "actor")

    assert len(await service.list_tasks({"priority": "high"})) == 1
    dashboard = await service.dashboard()
    assert dashboard["total"] == 2
    assert dashboard["by_status"] == {"todo": 1, "done": 1}
    assert dashboard["member_workloads"][0]["average_progress"] == 50
    assert dashboard["member_workloads"][0]["estimated_remaining_days"] == 1
    assert dashboard["recent_progress"] == []

    updated = await service.update_task(
        (await service.list_tasks({"priority": "high"}))[0]["id"],
        {"add_entry": {"kind": "blocker", "content": "接口超时，先走备用通道"}},
    )
    assert updated["entries"][0]["kind"] == "blocker"
    dashboard = await service.dashboard()
    assert dashboard["recent_progress"][0]["content"] == "接口超时，先走备用通道"


async def test_member_is_assignment_resource_without_credentials() -> None:
    service = ProgressApplicationService(
        ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository()),
        MemoryResourceStorage(),
    )
    member = await service.create_member({"name": "Alice", "title": "Designer"})
    assert "username" not in member
    assert "password" not in member
    assert "user_id" not in member
    assert member["operator"] is False

    await service.update_member(member["id"], {"active": False})
    try:
        await service.create_task({"title": "Cannot assign", "assignee_id": member["id"]}, "actor")
    except ValueError as exc:
        assert "active team member" in str(exc)
    else:
        raise AssertionError("inactive member assignment should fail")


async def test_operator_member_is_assignable_and_protected() -> None:
    service = ProgressApplicationService(
        ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository()),
        MemoryResourceStorage(),
    )
    await service.initialize(
        {"id": "user-1", "username": "admin", "display_name": "Administrator"}
    )
    members = await service.list_members()
    assert members[0]["operator"] is True
    assert members[0]["name"] == "管理员"
    assert members[0]["title"] == "工作台管理员"
    assert "user_id" not in members[0]

    await service.initialize(
        {"id": "user-1", "username": "admin", "display_name": "Administrator"}
    )
    assert len(await service.list_members()) == 1

    operator_id = members[0]["id"]
    task = await service.create_task({"title": "自己做", "assignee_id": operator_id}, "user-1")
    assert task["assignee_id"] == operator_id

    try:
        await service.update_member(operator_id, {"active": False})
    except ValueError as exc:
        assert "operator" in str(exc)
    else:
        raise AssertionError("operator deactivation should fail")

    try:
        await service.delete_member(operator_id)
    except ValueError as exc:
        assert "operator" in str(exc)
    else:
        raise AssertionError("operator deletion should fail")


async def test_operator_claims_existing_member_with_same_name() -> None:
    service = ProgressApplicationService(
        ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository()),
        MemoryResourceStorage(),
    )
    existing = await service.create_member({"name": "管理员", "title": "临时"})
    await service.initialize(
        {"id": "user-1", "username": "admin", "display_name": "Administrator"}
    )
    members = await service.list_members()
    assert len(members) == 1
    assert members[0]["id"] == existing["id"]
    assert members[0]["operator"] is True
    assert members[0]["title"] == "临时"


async def test_task_attachments_and_cleanup() -> None:
    storage = MemoryResourceStorage()
    service = ProgressApplicationService(
        ProgressDomainService(MemoryTaskRepository(), MemoryMemberRepository(), MemoryProjectRepository()),
        storage,
    )
    task = await service.create_task({"title": "登录页"}, "actor")
    with_file = await service.attach_file(task["id"], "shot.png", b"png-bytes")
    with_link = await service.attach_link(
        task["id"], "设计稿", "https://example.test/spec"
    )
    assert with_file["resources"][0]["kind"] == "image"
    assert with_link["resources"][1]["url"] == "https://example.test/spec"
    assert list(storage.files.values()) == [b"png-bytes"]

    stored = await service.open_resource_file(task["id"], with_file["resources"][0]["id"])
    assert stored.data == b"png-bytes"
    assert stored.inline is True

    await service.detach_resource(task["id"], with_file["resources"][0]["id"])
    assert storage.files == {}
    remaining = await service.attach_file(task["id"], "notes.md", b"# notes")
    await service.delete_task(task["id"])
    assert storage.files == {}
    assert remaining["resources"][-1]["kind"] == "document"
