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
    """Verify that legacy encodings are tried when UTF-8 fails.

    When a file is not encoded in UTF-8, the helper should still decode the
    contents by trying the legacy encodings such as Latin-1 before raising.
    """
    path = sandbox_dir / "legacy.json"
    path.write_bytes("café".encode("latin-1"))
    text = utils.read_text(path)
    assert text == "café"


def test_read_text_raises_when_encodings_fail(sandbox_dir: Path) -> None:
    """Raise ParserDecodingError when the explicit encodings all fail.

    If the caller provides a custom list of encodings and none of them match
    the file contents, the helper escalates with ParserDecodingError so the
    failure context is clear.
    """
    path = sandbox_dir / "invalid.bin"
    path.write_bytes(b"\xff")
    with pytest.raises(ParserDecodingError, match="Could not decode"):
        utils.read_text(path, encodings=("utf-16",))


def test_parse_mapping_wraps_loader_errors(sandbox_dir: Path) -> None:
    """Wrap loader failures in ParserSyntaxError.

    Any exception raised by the loader should be caught and re-raised as the
    shared syntax error so the loader pipeline only needs to handle one
    failure class.
    """
    path = sandbox_dir / "silent.json"
    path.write_text("{}")

    def _boom(_: str) -> None:
        message = "boom"
        raise ValueError(message)

    with pytest.raises(ParserSyntaxError, match="Failed to parse"):
        utils.parse_mapping(path, _boom)


def test_ensure_mapping_rejects_non_mapping(sandbox_dir: Path) -> None:
    """Reject non-mapping parser outputs with a ParserTypeError.

    The helper enforces the expectation that loaders always return dictionaries
    by rejecting sequences before they can propagate further into the pipeline.
    """
    path = sandbox_dir / "list.json"
    path.write_text("[]")
    with pytest.raises(ParserTypeError, match="expected a mapping"):
        utils.ensure_mapping([], path)


def test_ensure_mapping_accepts_mapping(sandbox_dir: Path) -> None:
    """Accept mappings produced by loaders and return a copy.

    When provided with a mapping the helper should return a fresh dict so the
    caller can mutate it safely while preserving the original loader output.
    """
    path = sandbox_dir / "mapping.json"
    path.write_text("{}")
    assert utils.ensure_mapping({"key": "value"}, path) == {"key": "value"}


def test_read_text_handles_utf8_bom(sandbox_dir: Path) -> None:
    """Honor UTF-8 files that start with a BOM.

    Files that include a UTF-8 BOM must still decode cleanly so downstream
    parsers can work with the text without a byte-order marker prefix.
    """
    path = sandbox_dir / "bom.txt"
    path.write_bytes(codecs.BOM_UTF8 + b"hello")
    assert utils.read_text(path) == "hello"


def test_read_text_handles_utf16_bom(sandbox_dir: Path) -> None:
    """Honor UTF-16 files that include a BOM.

    A BOM-marked UTF-16 file should be detected by `_default_encodings` and
    decoded via the correct UTF-16 decoder so characters such as “é” survive.
    """
    path = sandbox_dir / "utf16.txt"
    path.write_bytes("café".encode("utf-16"))
    assert utils.read_text(path) == "café"


def test_read_text_handles_utf32_bom(sandbox_dir: Path) -> None:
    """Honor UTF-32 files that include a BOM.

    The helper needs to try UTF-32 when the BOM indicates that encoding so the
    payload can be decoded without garbling the text.
    """
    path = sandbox_dir / "utf32.txt"
    path.write_bytes("data".encode("utf-32"))
    assert utils.read_text(path) == "data"


def test_read_text_respects_explicit_encodings(sandbox_dir: Path) -> None:
    """Respect an explicit encoding list when supplied.

    When callers provide their own candidate encodings, the helper should use
    that list instead of the default search order so trusted encodings succeed
    predictably.
    """
    path = sandbox_dir / "explicit.json"
    path.write_bytes("café".encode("latin-1"))
    assert utils.read_text(path, encodings=("latin-1",)) == "café"
