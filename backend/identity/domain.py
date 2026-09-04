from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
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


class IdentityDomainService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

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
