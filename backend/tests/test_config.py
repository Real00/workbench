from pathlib import Path

from shared.config import Settings


def test_workbench_environment_prefix_and_static_compatibility(monkeypatch) -> None:
    monkeypatch.setenv("WORKBENCH_MONGO_DATABASE", "custom-workbench")
    monkeypatch.setenv("STATIC_DIR", "/tmp/workbench-static")
    settings = Settings()
    assert settings.mongo_database == "custom-workbench"
    assert settings.static_dir == Path("/tmp/workbench-static")
