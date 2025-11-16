"""Story 3: Pydantic validation with defaults and overrides."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from fig_jam import ConfigValidationError, get_config

pytest.importorskip("pydantic")
from pydantic import BaseModel


def test_story_03_pydantic_validation_with_overrides(
    write_config: Callable[[str, str], Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expect clear errors then success once overrides exist."""
    config_path = write_config(
        "app_settings.json",
        """{
  "database": {
    "host": "db.company.local",
    "port": 5432
  },
  "nas_paths": {
    "shared_drive_dir": "/mnt/shared/",
    "backup_dir": "/mnt/backup/"
  },
  "logging": {
    "level": "INFO"
  }
}
""",
    )

    class DatabaseConfig(BaseModel):
        host: str
        port: int
        user: str = "admin"
        password: str
        __env_overrides__ = {"password": "APP_DB_PASSWORD"}

    with pytest.raises(ConfigValidationError) as excinfo:
        get_config(
            path=config_path,
            section="database",
            validator=DatabaseConfig,
        )
    assert str(config_path) in excinfo.value.context["failing_paths"]

    monkeypatch.setenv("APP_DB_PASSWORD", "secure_db_pass")

    result = get_config(
        path=config_path,
        section="database",
        validator=DatabaseConfig,
    )

    assert isinstance(result, DatabaseConfig)
    assert result.host == "db.company.local"
    assert result.port == 5432
    assert result.user == "admin"
    assert result.password == "secure_db_pass"  # noqa: S105
