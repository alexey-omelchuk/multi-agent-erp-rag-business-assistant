import pytest
from pydantic import ValidationError

from app.config import BASE_DIR, Settings


def test_defaults():
    settings = Settings()
    assert settings.memory_max_interactions >= 1
    assert ":" in settings.model


def test_env_overrides_default(monkeypatch):
    monkeypatch.setenv("PRODUCTION_API_URL", "http://production-api:8001")
    assert Settings().production_api_url == "http://production-api:8001"


def test_invalid_value_is_rejected(monkeypatch):
    monkeypatch.setenv("MEMORY_MAX_INTERACTIONS", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_resolve_makes_paths_absolute():
    settings = Settings()
    resolved = settings.resolve(settings.northwind_db_path)
    assert resolved.is_absolute()
    assert resolved == BASE_DIR / "data" / "northwind.db"
