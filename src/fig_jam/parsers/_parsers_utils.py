"""Shared helper utilities for the parser implementations."""

from __future__ import annotations

import codecs
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from fig_jam.parsers._parsers_errors import (
    ParserDecodingError,
    ParserSyntaxError,
    ParserTypeError,
)

ParserLoader = Callable[[str], Any]

_UTF16_BOMS = (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)
_UTF32_BOMS = (codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)


def _default_encodings(data: bytes) -> tuple[str, ...]:
    """Build the default encoding candidates for a file."""
    candidates: list[str] = []
    if data.startswith(codecs.BOM_UTF8):
        candidates.append("utf-8-sig")
    candidates.append("utf-8")
    candidates.extend(_bom_based_encodings(data))
    candidates.extend(("ascii", "latin-1", "cp1252"))
    return tuple(candidates)


def _bom_based_encodings(data: bytes) -> list[str]:
    """Return encodings implied by BOM markers."""
    if any(data.startswith(bom) for bom in _UTF32_BOMS):
        return ["utf-32"]
    if any(data.startswith(bom) for bom in _UTF16_BOMS):
        return ["utf-16"]
    return []


def _try_decode(
    data: bytes, encoding: str
) -> tuple[str | None, UnicodeDecodeError | None]:
    """Attempt to decode bytes with the provided encoding."""
    try:
        return data.decode(encoding), None
    except UnicodeDecodeError as error:
        return None, error


def read_text(path: Path, encodings: Sequence[str] | None = None) -> str:
    """Read text from a file while trying multiple encodings.

    Args:
        path: Path to the file being read.
        encodings: Optional override for the search order of encodings.

    Returns:
        Text decoded using the first encoding that succeeds.

    Raises:
        ParserDecodingError: If none of the encodings can decode the file.
    """
    data = path.read_bytes()
    attempted = tuple(encodings) if encodings else _default_encodings(data)
    last_error: UnicodeDecodeError | None = None
    for encoding in attempted:
        decoded, error = _try_decode(data, encoding)
        if decoded is not None:
            return decoded
        last_error = error
    raise ParserDecodingError(path, attempted) from last_error


def parse_mapping(path: Path, loader: ParserLoader) -> dict[str, Any]:
    """Parse text read from a file into a mapping.

    Args:
        path: File to be parsed.
        loader: Callable that transforms text into a Python object.

    Returns:
        Mapping produced by the loader.

    Raises:
        ParserSyntaxError: When the loader fails due to invalid syntax.
        ParserTypeError: When the loader returns a non-mapping value.
    """
    text = read_text(path)
    try:
        value = loader(text)
    except Exception as error:
        raise ParserSyntaxError(path, error) from error
    return ensure_mapping(value, path)


def ensure_mapping(value: Any, path: Path) -> dict[str, Any]:
    """Ensure that the parsed value is a mapping.

    Args:
        value: Parsed object produced by a loader.
        path: Source file that produced the value.

    Returns:
        A fresh dictionary populated with the contents of the mapping.

    Raises:
        ParserTypeError: When the parsed value is not a mapping.
    """
    if isinstance(value, Mapping):
        return dict(value)
    raise ParserTypeError(path, type(value))
