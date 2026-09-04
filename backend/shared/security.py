import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from cryptography.fernet import Fernet


class SecurityService:
    def __init__(self, secret: str, ttl_seconds: int, encryption_key: str | None = None):
        self.secret = secret
        self.ttl_seconds = ttl_seconds
        self.passwords = PasswordHasher()
        key = (
            encryption_key.encode()
            if encryption_key
            else base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        )
        self.cipher = Fernet(key)

    def hash_password(self, password: str) -> str:
        return self.passwords.hash(password)

    def verify_password(self, hashed: str, password: str) -> bool:
        try:
            return self.passwords.verify(hashed, password)
        except Exception:
            return False

    def issue_access_token(self, subject: str, role: str) -> str:
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "sub": subject,
                "role": role,
                "iat": now,
                "exp": now + timedelta(seconds=self.ttl_seconds),
            },
            self.secret,
            algorithm="HS256",
        )

    def issue_preview_token(
        self, payload: dict[str, Any], ttl_seconds: int, purpose: str = "ai-preview"
    ) -> str:
        now = datetime.now(UTC)
        claims = {
            **payload,
            "purpose": purpose,
            "nonce": secrets.token_urlsafe(12),
            "iat": now,
            "exp": now + timedelta(seconds=ttl_seconds),
        }
        return jwt.encode(claims, self.secret, algorithm="HS256")

    def decode_token(self, token: str, purpose: str | None = None) -> dict[str, Any]:
        payload = jwt.decode(token, self.secret, algorithms=["HS256"])
        if purpose and payload.get("purpose") != purpose:
            raise ValueError("invalid token purpose")
        return payload

    def encrypt(self, value: str) -> str:
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self.cipher.decrypt(value.encode()).decode()


def mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}{'*' * (len(value) - 7)}{value[-4:]}"
