from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Workbench"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_database: str = "workbench"
    jwt_secret: str = "change-me-in-production-with-32-bytes"
    jwt_ttl_seconds: int = 86_400
    preview_ttl_seconds: int = 600
    encryption_key: str | None = None
    admin_username: str = "admin"
    admin_password: str = "admin123!"
    static_dir: Path = Field(
        default=Path(__file__).parents[1] / "static",
        validation_alias=AliasChoices("WORKBENCH_STATIC_DIR", "STATIC_DIR"),
    )
    upload_dir: Path = Field(
        default=Path(__file__).parents[2] / "data" / "uploads",
        validation_alias=AliasChoices("WORKBENCH_UPLOAD_DIR", "UPLOAD_DIR"),
    )
    knowledge_dir: Path = Field(
        default=Path(__file__).parents[2] / "data" / "knowledge",
        validation_alias=AliasChoices("WORKBENCH_KNOWLEDGE_DIR", "KNOWLEDGE_DIR"),
    )
    model_config = SettingsConfigDict(
        env_prefix="WORKBENCH_", env_file=".env", extra="ignore", populate_by_name=True
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
