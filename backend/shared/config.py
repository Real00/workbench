from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import AliasChoices, BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _empty_path_as_none(value: object) -> object:
    if value is None or value == "":
        return None
    return value


OptionalPath = Annotated[Path | None, BeforeValidator(_empty_path_as_none)]


class Settings(BaseSettings):
    app_name: str = "Workbench"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_database: str = "workbench"
    jwt_secret: str = "change-me-in-production-with-32-bytes"
    jwt_ttl_seconds: int = 604_800  # 7 天；设备凭证仍可在过期后静默换发
    preview_ttl_seconds: int = 600
    encryption_key: str | None = None
    admin_username: str = "admin"
    admin_password: str = "admin123!"
    dev_auth_bypass: bool = False
    dev_api_port: int = 8080
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
    git_sha: str = "unknown"
    built_at: str = ""
    update_control_dir: OptionalPath = None
    update_agent_token: str = ""
    update_github_repo: str = "real00/workbench"
    update_github_ref: str = "main"
    update_github_token: str = ""
    model_config = SettingsConfigDict(
        env_prefix="WORKBENCH_", env_file=".env", extra="ignore", populate_by_name=True
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


# macOS WKWebView 多为 tauri://；Win/Linux/Android 为 http(s)://tauri.localhost
TAURI_DEFAULT_ORIGINS = (
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
)


def cors_origin_set(cors_origins: str) -> frozenset[str]:
    """解析逗号分隔的放行来源，统一去掉尾部斜杠。

    Tauri 壳（桌面 / Android）的默认来源始终放行：自定义 scheme 无法被网页伪造，
    不构成跨源风险；这样打包的客户端无需额外配置即可连接后端。
    """
    origins = {
        origin.strip().rstrip("/")
        for origin in cors_origins.split(",")
        if origin.strip()
    }
    origins.update(TAURI_DEFAULT_ORIGINS)
    return frozenset(origins)
