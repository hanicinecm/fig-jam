"""Fixtures shared by all integration tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture(name="integration_home")
def integration_home_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Provide a temporary home directory for the integration scenarios."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture(name="write_config")
def write_config_fixture(
    integration_home: Path,
) -> Callable[[str, str], Path]:
    """Return a helper that writes config files inside the integration home."""

    def _writer(filename: str, contents: str) -> Path:
        path = integration_home / filename
        path.write_text(contents, encoding="utf-8")
        return path

    return _writer
