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
    cors_origins: str = Field(
        default="",
        validation_alias=AliasChoices("WORKBENCH_CORS_ORIGINS", "CORS_ORIGINS"),
    )
    model_config = SettingsConfigDict(
        env_prefix="WORKBENCH_", env_file=".env", extra="ignore", populate_by_name=True
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


TAURI_DEFAULT_ORIGINS = ("tauri://localhost", "http://tauri.localhost")


def cors_origin_set(cors_origins: str) -> frozenset[str]:
    """解析逗号分隔的放行来源，统一去掉尾部斜杠。

    Tauri 桌面壳的默认来源始终放行：自定义 scheme 无法被网页伪造，
    不构成跨源风险；这样打包的桌面应用无需额外配置即可连接后端。
    """
    origins = {
        origin.strip().rstrip("/")
        for origin in cors_origins.split(",")
        if origin.strip()
    }
    origins.update(TAURI_DEFAULT_ORIGINS)
    return frozenset(origins)
