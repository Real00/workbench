from pathlib import Path

from shared.config import Settings, cors_origin_set


def test_workbench_environment_prefix_and_static_compatibility(monkeypatch) -> None:
    monkeypatch.setenv("WORKBENCH_MONGO_DATABASE", "custom-workbench")
    monkeypatch.setenv("STATIC_DIR", "/tmp/workbench-static")
    settings = Settings()
    assert settings.mongo_database == "custom-workbench"
    assert settings.static_dir == Path("/tmp/workbench-static")


def test_update_control_dir_empty_string_is_none(monkeypatch) -> None:
    monkeypatch.setenv("WORKBENCH_UPDATE_CONTROL_DIR", "")
    settings = Settings(_env_file=None)
    assert settings.update_control_dir is None


def test_cors_always_allows_tauri_desktop_origins() -> None:
    origins = cors_origin_set("")
    assert "tauri://localhost" in origins
    assert "http://tauri.localhost" in origins
    assert "https://tauri.localhost" in origins
    assert "https://web.example" in cors_origin_set("https://web.example/")
