"""Tests for the parser registry utilities."""

from __future__ import annotations

import types
from pathlib import Path

import pytest

from fig_jam.parsers import _parsers as parsers_module
from fig_jam.parsers import get_parser, iter_supported_suffixes
from fig_jam.parsers._parsers import (
    _parse_ini,
    _parse_json,
    _parse_toml,
    _parse_yaml,
    register_parser,
)
from fig_jam.parsers._parsers_errors import (
    ParserDependencyError,
    ParserSyntaxError,
    ParserTypeError,
)


def test_iter_supported_suffixes_includes_known_formats() -> None:
    """Expose the supported suffix set."""
    suffixes = set(iter_supported_suffixes())
    assert {".ini", ".cfg", ".json", ".toml", ".yaml", ".yml"} <= suffixes


def test_get_parser_returns_registered_function() -> None:
    """Return the JSON parser for the .json suffix."""
    assert get_parser(".json") is _parse_json


def test_get_parser_raises_for_unknown_suffix() -> None:
    """Raise ValueError when no parser handles the suffix."""
    with pytest.raises(ValueError, match="No parser registered for suffix"):
        get_parser(".unknown")


def test_register_parser_decorator() -> None:
    """Raise ValueError when registering a parser."""
    with pytest.raises(ValueError, match="Suffixes must start with a dot"):
        register_parser("invalid_suffix")

    with pytest.raises(ValueError, match="A parser is already registered"):
        register_parser(".json")


def test_parse_yaml_returns_mapping(sandbox_dir: Path) -> None:
    """Return a mapping for valid YAML input."""
    path = sandbox_dir / "config.yaml"
    path.write_text("key: value")
    assert _parse_yaml(path) == {"key": "value"}


def test_parse_yaml_raises_syntax_error(sandbox_dir: Path) -> None:
    """Raise ParserSyntaxError for malformed YAML."""
    path = sandbox_dir / "broken.yaml"
    path.write_text("key: [unterminated")
    with pytest.raises(ParserSyntaxError, match="Failed to parse"):
        _parse_yaml(path)


def test_parse_yaml_rejects_non_mapping(sandbox_dir: Path) -> None:
    """Reject YAML documents that do not produce a mapping."""
    path = sandbox_dir / "sequence.yaml"
    path.write_text("- one\n- two")
    with pytest.raises(ParserTypeError, match="expected a mapping"):
        _parse_yaml(path)


def test_parse_yaml_requires_pyyaml(
    sandbox_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise ParserDependencyError when PyYAML is unavailable."""
    monkeypatch.setattr(parsers_module, "yaml", None)
    path = sandbox_dir / "missing.yaml"
    path.write_text("key: value")
    with pytest.raises(ParserDependencyError, match="uv add pyyaml"):
        _parse_yaml(path)


def test_parse_toml_returns_mapping(sandbox_dir: Path) -> None:
    """Return a mapping for valid TOML input."""
    path = sandbox_dir / "config.toml"
    path.write_text('key = "value"')
    assert _parse_toml(path) == {"key": "value"}


def test_parse_toml_raises_syntax_error(sandbox_dir: Path) -> None:
    """Raise ParserSyntaxError for malformed TOML."""
    path = sandbox_dir / "broken.toml"
    path.write_text("key = ")
    with pytest.raises(ParserSyntaxError, match="Failed to parse"):
        _parse_toml(path)


def test_parse_toml_requires_parser(
    monkeypatch: pytest.MonkeyPatch, sandbox_dir: Path
) -> None:
    """Raise ParserDependencyError when no TOML loader is available."""
    monkeypatch.setattr(parsers_module, "tomllib", None)
    monkeypatch.setattr(parsers_module, "tomli", None)
    path = sandbox_dir / "missing.toml"
    path.write_text('key = "value"')
    with pytest.raises(ParserDependencyError, match="uv add tomli"):
        _parse_toml(path)


def test_parse_toml_uses_tomli_when_tomllib_missing(
    monkeypatch: pytest.MonkeyPatch, sandbox_dir: Path
) -> None:
    """Use the tomli loader when tomllib is absent."""
    path = sandbox_dir / "tomli.toml"
    path.write_text('key = "value"')

    def _tomli_loader(_: str) -> dict[str, str]:
        return {"tomli": "ok"}

    tomli_stub = types.SimpleNamespace(loads=_tomli_loader)
    monkeypatch.setattr(parsers_module, "tomllib", None)
    monkeypatch.setattr(parsers_module, "tomli", tomli_stub)
    assert _parse_toml(path) == {"tomli": "ok"}


def test_parse_json_returns_mapping(sandbox_dir: Path) -> None:
    """Return a mapping for valid JSON files."""
    path = sandbox_dir / "config.json"
    path.write_text('{"key": "value"}')
    assert _parse_json(path) == {"key": "value"}


def test_parse_json_raises_syntax_error(sandbox_dir: Path) -> None:
    """Raise ParserSyntaxError for invalid JSON."""
    path = sandbox_dir / "broken.json"
    path.write_text('{"key": }')
    with pytest.raises(ParserSyntaxError, match="Failed to parse"):
        _parse_json(path)


def test_parse_json_rejects_non_mapping(sandbox_dir: Path) -> None:
    """Reject JSON that does not produce a mapping."""
    path = sandbox_dir / "list.json"
    path.write_text("[1, 2, 3]")
    with pytest.raises(ParserTypeError, match="expected a mapping"):
        _parse_json(path)


def test_parse_ini_returns_mapping(sandbox_dir: Path) -> None:
    """Return a mapping for a simple INI file."""
    path = sandbox_dir / "config.ini"
    path.write_text("[section]\nkey = value")
    assert _parse_ini(path) == {"section": {"key": "value"}}


def test_parse_ini_includes_defaults(sandbox_dir: Path) -> None:
    """Expose DEFAULT values alongside other sections."""
    path = sandbox_dir / "config.ini"
    path.write_text("[DEFAULT]\nroot = base\n\n[section]\nvalue = test")
    parsed = _parse_ini(path)
    assert parsed["DEFAULT"] == {"root": "base"}
    assert parsed["section"] == {"root": "base", "value": "test"}


def test_parse_ini_preserves_case(sandbox_dir: Path) -> None:
    """Maintain the original case for both section keys and option names."""
    path = sandbox_dir / "config.ini"
    path.write_text(
        "[Section]\nUpperKey = Value\nlowerkey = other\n\n[section]\nLowerKey = diff"
    )
    parsed = _parse_ini(path)
    assert "Section" in parsed
    assert "section" in parsed
    assert parsed["Section"] == {"UpperKey": "Value", "lowerkey": "other"}
    assert parsed["section"] == {"LowerKey": "diff"}


def test_parse_ini_raises_syntax_error(sandbox_dir: Path) -> None:
    """Raise ParserSyntaxError when the INI syntax is invalid."""
    path = sandbox_dir / "broken.ini"
    path.write_text("key = value")
    with pytest.raises(ParserSyntaxError, match="Failed to parse"):
        _parse_ini(path)
