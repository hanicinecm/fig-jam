"""Shared fixtures for the parser tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sandbox_dir(tmp_path: Path) -> Path:
    """Return a sandbox directory for temporary config files."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    return sandbox
