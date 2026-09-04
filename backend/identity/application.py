from dataclasses import asdict
from typing import Any

from identity.domain import IdentityDomainService
from shared.security import SecurityService


def public_user(user: Any) -> dict[str, Any]:
    data = asdict(user)
    data.pop("password_hash", None)
    return data


class IdentityApplicationService:
    def __init__(
        self,
        domain: IdentityDomainService,
        security: SecurityService,
    ):
        self.domain = domain
        self.security = security

    async def initialize_admin(self, username: str, password: str) -> None:
        await self.domain.ensure_indexes()
        await self.domain.initialize_admin(
            username, self.security.hash_password(password), "Administrator"
        )

    async def get_by_username(self, username: str) -> dict[str, Any] | None:
        user = await self.domain.authenticate(username)
        return public_user(user) if user else None

    async def login(self, username: str, password: str) -> dict[str, Any]:
        user = await self.domain.authenticate(username)
        if (
            not user
            or not user.active
            or user.role != "admin"
            or not self.security.verify_password(user.password_hash, password)
        ):
            raise PermissionError("invalid credentials")
        return {
            "access_token": self.security.issue_access_token(user.id, user.role),
            "token_type": "Bearer",
            "user": public_user(user),
        }
