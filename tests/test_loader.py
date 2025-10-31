"""Integration tests for the loader pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from fig_jam.cache import clear_cache
from fig_jam.exceptions import (
    ConfigSourceAmbiguityError,
    ConfigSourceNotFoundError,
    ConfigValidationError,
)
from fig_jam.loader import get_config


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """Ensure the loader cache is clear before and after each test."""
    clear_cache()
    yield
    clear_cache()


def test_get_config_basic_file(tmp_path: Path) -> None:
    """Load configuration from a specific JSON file."""
    path = tmp_path / "config.json"
    path.write_text('{"feature": "fig"}', encoding="utf-8")

    result = get_config(path=path)

    assert dict(result) == {"feature": "fig"}


def test_get_config_with_section_and_validator(tmp_path: Path) -> None:
    """Extract a section and validate using a dict validator."""
    path = tmp_path / "settings.json"
    path.write_text(
        '{"database": {"host": "db.local", "port": "5432"}, "other": true}',
        encoding="utf-8",
    )

    result = get_config(
        path=path,
        section="database",
        validator={"host": str, "port": int},
    )

    assert dict(result) == {"host": "db.local", "port": 5432}


def test_get_config_not_found(tmp_path: Path) -> None:
    """Raise a not-found error when no candidates exist."""
    with pytest.raises(ConfigSourceNotFoundError):
        get_config(path=tmp_path / "missing.json")


def test_get_config_ambiguity(tmp_path: Path) -> None:
    """Raise an ambiguity error when multiple candidates succeed."""
    (tmp_path / "one.json").write_text('{"feature": "fig"}', encoding="utf-8")
    (tmp_path / "two.yaml").write_text("feature: fig", encoding="utf-8")

    with pytest.raises(ConfigSourceAmbiguityError):
        get_config(path=tmp_path)


def test_get_config_validation_error(tmp_path: Path) -> None:
    """Raise validation error when candidates fail schema checks."""
    path = tmp_path / "config.json"
    path.write_text('{"feature": "fig"}', encoding="utf-8")

    with pytest.raises(ConfigValidationError):
        get_config(path=path, validator={"missing": str})


def test_get_config_cache_and_clear(tmp_path: Path) -> None:
    """Cache results across calls and respect manual invalidation."""
    path = tmp_path / "config.json"
    path.write_text('{"feature": "fig"}', encoding="utf-8")

    first = get_config(path=path)
    assert dict(first) == {"feature": "fig"}

    path.write_text('{"feature": "jam"}', encoding="utf-8")
    cached = get_config(path=path)
    assert dict(cached) == {"feature": "fig"}

    clear_cache()
    refreshed = get_config(path=path)
    assert dict(refreshed) == {"feature": "jam"}
