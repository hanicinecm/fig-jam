"""Tests for the parser registry and format-specific parsers."""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from fig_jam.parsers import (
    get_registered_parser,
    iter_registered_suffixes,
    parse_ini,
    parse_json,
    parse_toml,
    parse_yaml,
)


def _toml_dependency_available() -> bool:
    """Determine whether a TOML parser dependency is installed."""
    return any(
        importlib.util.find_spec(module_name) is not None
        for module_name in ("tomllib", "tomli")
    )


def test_iter_registered_suffixes_includes_known_formats() -> None:
    """Ensure known parser suffixes are registered."""
    suffixes = set(iter_registered_suffixes())
    assert {".json", ".toml", ".ini", ".cfg", ".yaml", ".yml"} <= suffixes


def test_get_registered_parser_returns_callable() -> None:
    """Verify parser retrieval resolves to the correct callable."""
    parser = get_registered_parser(".json")
    assert parser is parse_json


def test_parse_json_success(tmp_path: Path) -> None:
    """Parse UTF-8 JSON mapping successfully."""
    path = tmp_path / "config.json"
    path.write_text('{"feature": "fig"}', encoding="utf-8")

    result = parse_json(path)

    assert result.success is True
    assert dict(result.data or {}) == {"feature": "fig"}
    detail = result.diagnostics[0]
    assert detail.stage == "parsers.json"
    assert detail.data["encoding"] == "utf-8"
    assert detail.data["attempted_encodings"] == ("utf-8",)


def test_parse_json_utf16_fallback(tmp_path: Path) -> None:
    """Use fallback encoding when JSON file is UTF-16."""
    path = tmp_path / "config.json"
    path.write_text('{"feature": "jam"}', encoding="utf-16")

    result = parse_json(path)

    assert result.success is True
    assert dict(result.data or {}) == {"feature": "jam"}
    detail = result.diagnostics[0]
    assert detail.data["encoding"] in {"utf-16", "utf-16-le", "utf-16-be"}
    attempts = detail.data["attempted_encodings"]
    assert attempts[0] == "utf-8"
    assert detail.data["encoding"] == attempts[-1]


def test_parse_json_invalid_content(tmp_path: Path) -> None:
    """Return diagnostics when JSON content is malformed."""
    path = tmp_path / "config.json"
    path.write_text("{invalid json", encoding="utf-8")

    result = parse_json(path)

    assert result.success is False
    detail = result.diagnostics[0]
    assert detail.message == "Failed to parse JSON content."
    assert detail.data["lineno"] == 1
    assert detail.data["colno"] == 2


def test_parse_json_requires_mapping(tmp_path: Path) -> None:
    """Reject JSON files whose root is not a mapping."""
    path = tmp_path / "config.json"
    path.write_text('["one", "two"]', encoding="utf-8")

    result = parse_json(path)

    assert result.success is False
    detail = result.diagnostics[0]
    assert detail.message == "JSON root object must be a mapping."


def test_parse_toml_success(tmp_path: Path) -> None:
    """Parse TOML mapping successfully."""
    if not _toml_dependency_available():
        pytest.skip("TOML parser dependency unavailable")

    path = tmp_path / "config.toml"
    path.write_text('[feature]\nname = "fig"\n', encoding="utf-8")

    result = parse_toml(path)

    assert result.success is True
    data = result.data or {}
    assert dict(data["feature"]) == {"name": "fig"}


def test_parse_toml_missing_dependency(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Surface dependency diagnostics when TOML parser is unavailable."""
    path = tmp_path / "config.toml"
    path.write_text('[feature]\nname = "fig"\n', encoding="utf-8")

    def missing_loader() -> Mapping[str, Any]:
        message = "tomli"
        raise ModuleNotFoundError(message)

    monkeypatch.setattr("fig_jam.parsers._load_toml", missing_loader)

    result = parse_toml(path)

    assert result.success is False
    detail = result.diagnostics[0]
    assert detail.data["dependency"] == "tomli"
    assert detail.data["remediation"]


def test_parse_ini_success(tmp_path: Path) -> None:
    """Parse INI content including defaults."""
    path = tmp_path / "config.ini"
    path.write_text(
        "[DEFAULT]\nrole = primary\n\n[feature]\nname = fig\n",
        encoding="utf-8",
    )

    result = parse_ini(path)

    assert result.success is True
    data = dict(result.data or {})
    assert data["DEFAULT"] == {"role": "primary"}
    section = data["feature"]
    assert section["name"] == "fig"
    assert section["role"] == "primary"


def test_parse_ini_invalid(tmp_path: Path) -> None:
    """Return diagnostics for malformed INI."""
    path = tmp_path / "config.ini"
    path.write_text("name=fig\n:no_section\n", encoding="utf-8")

    result = parse_ini(path)

    assert result.success is False
    detail = result.diagnostics[0]
    assert detail.message == "Failed to parse INI content."


def test_parse_yaml_missing_dependency(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Surface dependency diagnostics when YAML parser is unavailable."""
    path = tmp_path / "config.yaml"
    path.write_text("feature: fig\n", encoding="utf-8")

    def missing_yaml_loader() -> Any:
        message = "pyyaml"
        raise ModuleNotFoundError(message)

    monkeypatch.setattr("fig_jam.parsers._load_yaml", missing_yaml_loader)

    result = parse_yaml(path)

    assert result.success is False
    detail = result.diagnostics[0]
    assert detail.data["dependency"] == "pyyaml"
    assert detail.data["remediation"]


def test_parse_yaml_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Parse YAML using the provided loader hook."""
    path = tmp_path / "config.yaml"
    path.write_text("feature: fig\n", encoding="utf-8")

    def fake_loader(text: str) -> Mapping[str, Any]:
        return {"feature": text.split(":", maxsplit=1)[1].strip()}

    monkeypatch.setattr("fig_jam.parsers._load_yaml", lambda: fake_loader)

    result = parse_yaml(path)

    assert result.success is True
    assert dict(result.data or {}) == {"feature": "fig"}


def test_parse_yaml_requires_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Reject YAML documents whose root is not a mapping."""
    path = tmp_path / "config.yaml"
    path.write_text("- fig\n- jam\n", encoding="utf-8")

    def fake_loader(_: str) -> list[str]:
        return ["fig", "jam"]

    monkeypatch.setattr("fig_jam.parsers._load_yaml", lambda: fake_loader)

    result = parse_yaml(path)

    assert result.success is False
    detail = result.diagnostics[0]
    assert detail.message == "YAML root object must be a mapping."
