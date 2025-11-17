"""Tests for the shared parser utilities."""

from __future__ import annotations

import codecs
from pathlib import Path

import pytest

from fig_jam.parsers import _parsers_utils as utils
from fig_jam.parsers._parsers_errors import (
    ParserDecodingError,
    ParserSyntaxError,
    ParserTypeError,
)


def test_read_text_falls_back_to_legacy_encoding(sandbox_dir: Path) -> None:
    """Verify that legacy encodings are tried when UTF-8 fails."""
    path = sandbox_dir / "legacy.json"
    path.write_bytes("café".encode("latin-1"))
    text = utils.read_text(path)
    assert text == "café"


def test_read_text_raises_when_encodings_fail(sandbox_dir: Path) -> None:
    """Raise when none of the supplied encodings decode the file."""
    path = sandbox_dir / "invalid.bin"
    path.write_bytes(b"\xff")
    with pytest.raises(ParserDecodingError, match="Could not decode"):
        utils.read_text(path, encodings=("utf-16",))


def test_parse_mapping_wraps_loader_errors(sandbox_dir: Path) -> None:
    """Wrap loader failures in ParserSyntaxError."""
    path = sandbox_dir / "silent.json"
    path.write_text("{}")

    def _boom(_: str) -> None:
        message = "boom"
        raise ValueError(message)

    with pytest.raises(ParserSyntaxError, match="Failed to parse"):
        utils.parse_mapping(path, _boom)


def test_ensure_mapping_rejects_non_mapping(sandbox_dir: Path) -> None:
    """Reject non-mapping parser outputs."""
    path = sandbox_dir / "list.json"
    path.write_text("[]")
    with pytest.raises(ParserTypeError, match="expected a mapping"):
        utils.ensure_mapping([], path)


def test_ensure_mapping_accepts_mapping(sandbox_dir: Path) -> None:
    """Accept mappings produced by loaders."""
    path = sandbox_dir / "mapping.json"
    path.write_text("{}")
    assert utils.ensure_mapping({"key": "value"}, path) == {"key": "value"}


def test_read_text_handles_utf8_bom(sandbox_dir: Path) -> None:
    """Honor UTF-8 files that start with a BOM."""
    path = sandbox_dir / "bom.txt"
    path.write_bytes(codecs.BOM_UTF8 + b"hello")
    assert utils.read_text(path) == "hello"


def test_read_text_handles_utf16_bom(sandbox_dir: Path) -> None:
    """Honor UTF-16 files that include a BOM."""
    path = sandbox_dir / "utf16.txt"
    path.write_bytes("café".encode("utf-16"))
    assert utils.read_text(path) == "café"


def test_read_text_handles_utf32_bom(sandbox_dir: Path) -> None:
    """Honor UTF-32 files that include a BOM."""
    path = sandbox_dir / "utf32.txt"
    path.write_bytes("data".encode("utf-32"))
    assert utils.read_text(path) == "data"


def test_read_text_respects_explicit_encodings(sandbox_dir: Path) -> None:
    """Respect an explicit encoding list when supplied."""
    path = sandbox_dir / "explicit.json"
    path.write_bytes("café".encode("latin-1"))
    assert utils.read_text(path, encodings=("latin-1",)) == "café"
