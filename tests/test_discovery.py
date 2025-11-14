"""Tests for the discovery pipeline."""

from __future__ import annotations

from pathlib import Path

from fig_jam.pipeline.discovery import discover_candidates


def test_discover_file_without_section(tmp_path: Path) -> None:
    """Discover a single JSON configuration file."""
    path = tmp_path / "config.json"
    path.write_text('{"feature": "fig"}', encoding="utf-8")

    result = discover_candidates(path, section=None)

    candidates = tuple(result)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.data is not None
    assert dict(candidate.data) == {"feature": "fig"}
    stages = [detail.stage for detail in candidate.diagnostics]
    assert stages[0] == "parsers.json"


def test_discover_directory_with_section(tmp_path: Path) -> None:
    """Extract a section from a discovered configuration."""
    path = tmp_path / "config.toml"
    path.write_text("[feature]\nname='jam'\n", encoding="utf-8")

    result = discover_candidates(tmp_path, section="feature")

    candidates = tuple(result)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.data is not None
    assert dict(candidate.data) == {"name": "jam"}
    stages = [detail.stage for detail in candidate.diagnostics]
    assert "discovery.section" in stages


def test_discover_missing_section(tmp_path: Path) -> None:
    """Surface diagnostics when a requested section is absent."""
    path = tmp_path / "config.json"
    path.write_text('{"feature": {"name": "fig"}}', encoding="utf-8")

    result = discover_candidates(path, section="missing")

    candidate = next(iter(result))
    assert candidate.data is None
    detail = candidate.diagnostics[-1]
    assert detail.stage == "discovery.section"
    assert "not found" in detail.message


def test_discover_nonexistent_path(tmp_path: Path) -> None:
    """Emit diagnostics for a path that does not exist."""
    missing = tmp_path / "config.json"

    result = discover_candidates(missing, section=None)

    candidate = next(iter(result))
    assert candidate.data is None
    detail = candidate.diagnostics[0]
    assert detail.stage == "discovery.enumeration"
    assert "does not exist" in detail.message


def test_discover_directory_without_supported_configs(tmp_path: Path) -> None:
    """Emit diagnostics when directory lacks supported files."""
    (tmp_path / "readme.txt").write_text("notes", encoding="utf-8")

    result = discover_candidates(tmp_path, section=None)

    candidate = next(iter(result))
    assert candidate.data is None
    detail = candidate.diagnostics[0]
    assert detail.stage == "discovery.enumeration"
    assert "supported extensions" in detail.message
