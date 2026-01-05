"""Shared helper utilities for the parser implementations.

This module offers the low-level helpers every parser uses for decoding files,
wrapping parser loaders, and enforcing the mapping contract so reloads stay
consistent. Because encoding detection and loader error handling are centralized
here, each format-specific module can stay focused on format details instead of
duplicating common plumbing.
"""

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
    """Build default encoding candidates by inspecting BOM markers.

    The order ensures BOM-aware decoders are tried first so files that
    explicitly declare UTF-8, UTF-16, or UTF-32 encodings are handled
    before falling back to more permissive encodings such as ASCII,
    Latin-1, and CP1252.
    """
    candidates: list[str] = []
    if data.startswith(codecs.BOM_UTF8):
        candidates.append("utf-8-sig")
    candidates.append("utf-8")
    candidates.extend(_bom_based_encodings(data))
    candidates.extend(("ascii", "latin-1", "cp1252"))
    return tuple(candidates)


def _bom_based_encodings(data: bytes) -> list[str]:
    """Return encoding names derived from the BOM if one is present.

    Toml, XML, and other formats may emit BOMs that unambiguously
    declare whether the file is UTF-16 or UTF-32. This helper keeps
    those decoder candidates near the front of the search order so the
    subsequent read does not misinterpret the byte order.
    """
    if any(data.startswith(bom) for bom in _UTF32_BOMS):
        return ["utf-32"]
    if any(data.startswith(bom) for bom in _UTF16_BOMS):
        return ["utf-16"]
    return []


def _try_decode(
    data: bytes, encoding: str
) -> tuple[str | None, UnicodeDecodeError | None]:
    """Attempt to decode data with the provided encoding and report failure.

    The helper returns a tuple containing the decoded text when
    successful or the raised UnicodeDecodeError so callers can learn why
    the candidate failed without raising immediately.
    """
    try:
        return data.decode(encoding), None
    except UnicodeDecodeError as error:
        return None, error


def read_text(path: Path, encodings: Sequence[str] | None = None) -> str:
    """Read text from a file while trying multiple encodings until decoding.

    Args:
        path: Path to the file being read.
        encodings: Optional override for the search order of encodings.

    Returns:
        Text decoded using the first encoding that succeeds.

    Raises:
        ParserDecodingError: If none of the encodings can decode the file.

    The helper tries candidate encodings until one succeeds so callers do
    not need to worry about BOM-aware or legacy encoding fallbacks.
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
    """Parse a configuration file into a mapping using the supplied loader.

    Args:
        path: File to be parsed.
        loader: Callable that transforms text into a Python object.

    Returns:
        Mapping produced by the loader.

    Raises:
        ParserSyntaxError: When the loader fails due to invalid syntax.
        ParserTypeError: When the loader returns a non-mapping value.

    The loader receives the fully decoded text and is expected to return a
    mapping that can be validated or merged into a larger snapshot. Errors
    from the loader are wrapped so callers only deal with parser-specific
    exceptions.
    """
    text = read_text(path)
    try:
        value = loader(text)
    except Exception as error:
        raise ParserSyntaxError(path, error) from error
    return ensure_mapping(value, path)


def ensure_mapping(value: Any, path: Path) -> dict[str, Any]:
    """Ensure that the parsed value is a mapping and provide a copy.

    Args:
        value: Parsed object produced by a loader.
        path: Source file that produced the value.

    Returns:
        A fresh dictionary populated with the contents of the mapping.

    Raises:
        ParserTypeError: When the parsed value is not a mapping.

    Mapping-like objects are copied into a plain dict before returning so
    downstream code can mutate the result without affecting loader-specific
    structures such as ConfigParser proxies.
    """
    if isinstance(value, Mapping):
        return dict(value)
    raise ParserTypeError(path, type(value))
