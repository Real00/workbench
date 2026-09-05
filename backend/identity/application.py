import hashlib
import hmac
import secrets
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from identity.domain import DeviceBinding, DeviceRepository, IdentityDomainService
from shared.security import SecurityService


def public_user(user: Any) -> dict[str, Any]:
    data = asdict(user)
    data.pop("password_hash", None)
    return data


def hash_device_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class IdentityApplicationService:
    def __init__(
        self,
        domain: IdentityDomainService,
        security: SecurityService,
        devices: DeviceRepository | None = None,
    ):
        self.domain = domain
        self.security = security
        self.devices = devices

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

    async def bind_device(self, user: dict[str, Any], device_id: str, device_name: str) -> str | None:
        """颁发设备长效凭证（仅返回一次原文，服务端只留哈希）。同设备重复绑定则轮换。"""
        if not self.devices:
            return None
        clean_id = str(device_id or "").strip()
        clean_name = str(device_name or "").strip()[:100]
        if not clean_id or not clean_name:
            return None
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        existing = await self.devices.by_device(clean_id)
        binding = DeviceBinding(
            id=existing.id if existing else str(uuid4()),
            user_id=str(user["id"]),
            device_id=clean_id,
            device_name=clean_name,
            token_hash=hash_device_token(token),
            created_at=existing.created_at if existing else now,
            last_active_at=now,
        )
        await self.devices.save(binding)
        return token

    async def login_with_device(self, device_id: str, device_token: str) -> dict[str, Any]:
        if not self.devices:
            raise PermissionError("device binding is not available")
        binding = await self.devices.by_device(str(device_id).strip())
        if (
            not binding
            or not hmac.compare_digest(binding.token_hash, hash_device_token(str(device_token)))
        ):
            raise PermissionError("invalid device credentials")
        user = await self.domain.get_user(binding.user_id)
        if not user or not user.active:
            raise PermissionError("invalid device credentials")
        binding.last_active_at = datetime.now(UTC)
        await self.devices.save(binding)
        return {
            "access_token": self.security.issue_access_token(user.id, user.role),
            "token_type": "Bearer",
            "user": public_user(user),
        }

    async def list_devices(self, user_id: str) -> list[dict[str, Any]]:
        if not self.devices:
            return []
        return [binding.public() for binding in await self.devices.list_for_user(user_id)]

    async def unbind_device(self, user_id: str, binding_id: str) -> None:
        if not self.devices:
            raise LookupError("device binding not found")
        if not await self.devices.delete(user_id, binding_id):
            raise LookupError("device binding not found")
