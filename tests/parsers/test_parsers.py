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
    """Ensure the suffix iterator advertises all built-in parsers.

    The returned set should contain the standard extensions so discovery can
    rely on the documented parsers instead of hardcoding names.
    """
    suffixes = set(iter_supported_suffixes())
    assert {".ini", ".cfg", ".json", ".toml", ".yaml", ".yml"} <= suffixes


def test_get_parser_returns_registered_function() -> None:
    """Return the JSON parser when querying the .json suffix.

    The helper should fetch the parser callable that was registered for
    JSON so subsequent stages can decode files without referencing the
    private registry directly.
    """
    assert get_parser(".json") is _parse_json


def test_get_parser_raises_for_unknown_suffix() -> None:
    """Raise ValueError when requesting a parser that does not exist.

    The error should reference the unknown suffix so callers understand why
    parsing cannot proceed for unsupported extensions.
    """
    with pytest.raises(ValueError, match="No parser registered for suffix"):
        get_parser(".unknown")


def test_register_parser_decorator() -> None:
    """Guard against invalid or duplicate suffix registrations.

    Invalid suffix names or attempts to register a parser for an already
    claimed extension should both raise, keeping the registry deterministic.
    """
    with pytest.raises(ValueError, match="Suffixes must start with a dot"):
        register_parser("invalid_suffix")

    with pytest.raises(ValueError, match="A parser is already registered"):
        register_parser(".json")


def test_parse_yaml_returns_mapping(sandbox_dir: Path) -> None:
    """Return a mapping for valid YAML input while using safe_load.

    The test checks that a simple key/value pair decodes into the expected
    dictionary so higher layers can rely on the YAML parser producing native
    mappings.
    """
    path = sandbox_dir / "config.yaml"
    path.write_text("key: value")
    assert _parse_yaml(path) == {"key": "value"}


def test_parse_yaml_raises_syntax_error(sandbox_dir: Path) -> None:
    """Raise ParserSyntaxError when the YAML content is invalid.

    Malformed YAML should be wrapped in a parser-specific syntax exception so
    consumers can report the failure without touching PyYAML internals.
    """
    path = sandbox_dir / "broken.yaml"
    path.write_text("key: [unterminated")
    with pytest.raises(ParserSyntaxError, match="Failed to parse"):
        _parse_yaml(path)


def test_parse_yaml_rejects_non_mapping(sandbox_dir: Path) -> None:
    """Reject YAML documents that do not produce a mapping.

    Ensuring only mappings are accepted keeps the parser contract consistent
    across formats, and non-mapping inputs should raise a ParserTypeError.
    """
    path = sandbox_dir / "sequence.yaml"
    path.write_text("- one\n- two")
    with pytest.raises(ParserTypeError, match="expected a mapping"):
        _parse_yaml(path)


def test_parse_yaml_requires_pyyaml(
    sandbox_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raise ParserDependencyError when PyYAML is unavailable.

    The parser should stop early if PyYAML cannot be imported and explain how
    to install the dependency rather than raising an ImportError later.
    """
    monkeypatch.setattr(parsers_module, "yaml", None)
    path = sandbox_dir / "missing.yaml"
    path.write_text("key: value")
    with pytest.raises(ParserDependencyError, match="uv add pyyaml"):
        _parse_yaml(path)


def test_parse_toml_returns_mapping(sandbox_dir: Path) -> None:
    """Return a mapping when parsing valid TOML input.

    TOML files should decode to the expected dictionary so the parsed output
    matches the data defined in the file and no extra normalization is needed.
    """
    path = sandbox_dir / "config.toml"
    path.write_text('key = "value"')
    assert _parse_toml(path) == {"key": "value"}


def test_parse_toml_raises_syntax_error(sandbox_dir: Path) -> None:
    """Raise ParserSyntaxError when TOML content is syntactically wrong.

    The helper must wrap the tomllib/tomli failure to keep error handling
    consistent with other parsers.
    """
    path = sandbox_dir / "broken.toml"
    path.write_text("key = ")
    with pytest.raises(ParserSyntaxError, match="Failed to parse"):
        _parse_toml(path)


def test_parse_toml_requires_parser(
    monkeypatch: pytest.MonkeyPatch, sandbox_dir: Path
) -> None:
    """Raise ParserDependencyError when no TOML loader is available.

    When both `tomllib` and `tomli` are missing, the parser should signal the
    missing dependency rather than attempting to decode.
    """
    monkeypatch.setattr(parsers_module, "tomllib", None)
    monkeypatch.setattr(parsers_module, "tomli", None)
    path = sandbox_dir / "missing.toml"
    path.write_text('key = "value"')
    with pytest.raises(ParserDependencyError, match="uv add tomli"):
        _parse_toml(path)


def test_parse_toml_uses_tomli_when_tomllib_missing(
    monkeypatch: pytest.MonkeyPatch, sandbox_dir: Path
) -> None:
    """Use the tomli loader when tomllib is absent.

    The parser should still succeed when tomli is provided as a fallback so
    older runtimes can continue parsing TOML files without the stdlib loader.
    """
    path = sandbox_dir / "tomli.toml"
    path.write_text('key = "value"')

    def _tomli_loader(_: str) -> dict[str, str]:
        return {"tomli": "ok"}

    tomli_stub = types.SimpleNamespace(loads=_tomli_loader)
    monkeypatch.setattr(parsers_module, "tomllib", None)
    monkeypatch.setattr(parsers_module, "tomli", tomli_stub)
    assert _parse_toml(path) == {"tomli": "ok"}


def test_parse_json_returns_mapping(sandbox_dir: Path) -> None:
    """Return a mapping for valid JSON files from the wrapper helper.

    Using `parse_mapping` should guarantee that valid JSON content yields the
    expected dictionary without additional transformation.
    """
    path = sandbox_dir / "config.json"
    path.write_text('{"key": "value"}')
    assert _parse_json(path) == {"key": "value"}


def test_parse_json_raises_syntax_error(sandbox_dir: Path) -> None:
    """Raise ParserSyntaxError when the JSON document is malformed.

    Syntax errors should be wrapped by `parse_mapping` so the caller receives
    a consistent parser exception regardless of the backend decoder.
    """
    path = sandbox_dir / "broken.json"
    path.write_text('{"key": }')
    with pytest.raises(ParserSyntaxError, match="Failed to parse"):
        _parse_json(path)


def test_parse_json_rejects_non_mapping(sandbox_dir: Path) -> None:
    """Reject JSON documents whose root object is not a mapping.

    The parser enforces the mapping contract, so non-mapping root values raise
    ParserTypeError even if the JSON is technically valid.
    """
    path = sandbox_dir / "list.json"
    path.write_text("[1, 2, 3]")
    with pytest.raises(ParserTypeError, match="expected a mapping"):
        _parse_json(path)


def test_parse_ini_returns_mapping(sandbox_dir: Path) -> None:
    """Return a mapping after parsing a simple INI document.

    The parser should convert each section into its own mapping so callers can
    consume the INI structure like any other configuration format.
    """
    path = sandbox_dir / "config.ini"
    path.write_text("[section]\nkey = value")
    assert _parse_ini(path) == {"section": {"key": "value"}}


def test_parse_ini_includes_defaults(sandbox_dir: Path) -> None:
    """Expose DEFAULT values alongside the explicitly defined sections.

    Default options should be surfaced under the `DEFAULT` key while other
    sections inherit those settings, mirroring ConfigParser's semantics.
    """
    path = sandbox_dir / "config.ini"
    path.write_text("[DEFAULT]\nroot = base\n\n[section]\nvalue = test")
    parsed = _parse_ini(path)
    assert parsed["DEFAULT"] == {"root": "base"}
    assert parsed["section"] == {"root": "base", "value": "test"}


def test_parse_ini_preserves_case(sandbox_dir: Path) -> None:
    """Maintain the original case for sections and option names.

    The loader must disable automatic lowercasing so configuration consumers
    relying on case-sensitive keys see the values as authored.
    """
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
    """Raise ParserSyntaxError when the INI syntax is invalid.

    Malformed INI files should trigger the shared syntax exception so the
    error message can highlight the problematic path.
    """
    path = sandbox_dir / "broken.ini"
    path.write_text("key = value")
    with pytest.raises(ParserSyntaxError, match="Failed to parse"):
        _parse_ini(path)
