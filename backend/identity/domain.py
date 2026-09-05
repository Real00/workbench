from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4


@dataclass
class User:
    id: str
    username: str
    password_hash: str
    display_name: str
    role: str
    active: bool
    created_at: datetime

    @classmethod
    def create(
        cls, username: str, password_hash: str, display_name: str, role: str = "member"
    ) -> "User":
        if not username.strip() or not display_name.strip():
            raise ValueError("username and display_name are required")
        if role not in {"admin", "member"}:
            raise ValueError("invalid role")
        return cls(
            str(uuid4()),
            username.strip(),
            password_hash,
            display_name.strip(),
            role,
            True,
            datetime.now(UTC),
        )

    def rename(self, display_name: str) -> None:
        if not display_name.strip():
            raise ValueError("display_name is required")
        self.display_name = display_name.strip()

    def set_active(self, active: bool) -> None:
        if self.role == "admin" and not active:
            raise ValueError("admin cannot be disabled")
        self.active = active


class UserRepository(Protocol):
    async def count(self) -> int: ...
    async def save(self, user: User) -> None: ...
    async def by_id(self, user_id: str) -> User | None: ...
    async def by_username(self, username: str) -> User | None: ...
    async def ensure_indexes(self) -> None: ...


@dataclass
class DeviceBinding:
    """设备绑定：登录一次后，该设备可凭长效凭证静默换发短期 JWT。

    token 只存 SHA-256 哈希，泄露原文也无法反查；解绑即失效。"""

    id: str
    user_id: str
    device_id: str
    device_name: str
    token_hash: str
    created_at: datetime
    last_active_at: datetime

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
        }


class DeviceRepository(Protocol):
    async def save(self, binding: DeviceBinding) -> None: ...
    async def by_device(self, device_id: str) -> DeviceBinding | None: ...
    async def list_for_user(self, user_id: str) -> list[DeviceBinding]: ...
    async def delete(self, user_id: str, binding_id: str) -> bool: ...
    async def ensure_indexes(self) -> None: ...


class IdentityDomainService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def get_user(self, user_id: str) -> User | None:
        return await self.repository.by_id(user_id)

    async def ensure_indexes(self) -> None:
        await self.repository.ensure_indexes()

    async def initialize_admin(
        self, username: str, password_hash: str, display_name: str
    ) -> User | None:
        if await self.repository.count():
            return None
        return await self.register_admin(username, password_hash, display_name)

    async def register_admin(self, username: str, password_hash: str, display_name: str) -> User:
        if await self.repository.by_username(username):
            raise ValueError("username already exists")
        user = User.create(username, password_hash, display_name, "admin")
        await self.repository.save(user)
        return user

    async def authenticate(self, username: str) -> User | None:
        return await self.repository.by_username(username)
