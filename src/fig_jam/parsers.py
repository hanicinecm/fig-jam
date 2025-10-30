"""Parser registry and format-specific parser interfaces for fig_jam."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

ParserCallable = Callable[[Path], Mapping[str, Any]]
ExtensionArg = str | Iterable[str]

_PARSER_REGISTRY: dict[str, ParserCallable] = {}


def _normalize_extension(extension: str) -> str:
    """Normalise an extension string to include a leading dot and lowercase."""
    if not extension:
        message = "Parser extension cannot be empty."
        raise ValueError(message)
    normalized = extension if extension.startswith(".") else f".{extension}"
    return normalized.lower()


def register_parser(
    *extensions: ExtensionArg,
) -> Callable[[ParserCallable], ParserCallable]:
    """Register a parser callable for one or more file extensions."""
    if not extensions:
        message = "At least one extension must be provided."
        raise ValueError(message)

    normalized_extensions: tuple[str, ...] = tuple(
        _normalize_extension(ext) for ext in _flatten_extensions(extensions)
    )

    def decorator(parser: ParserCallable) -> ParserCallable:
        for extension in normalized_extensions:
            existing = _PARSER_REGISTRY.get(extension)
            if existing is not None and existing is not parser:
                message = f"A parser is already registered for extension '{extension}'."
                raise ValueError(message)
            _PARSER_REGISTRY[extension] = parser
        return parser

    return decorator


def _flatten_extensions(raw_extensions: Iterable[ExtensionArg]) -> Iterator[str]:
    """Flatten potentially nested iterables of extensions."""
    for raw in raw_extensions:
        if isinstance(raw, str):
            yield raw
        else:
            yield from raw


def get_registered_parser(suffix: str) -> ParserCallable | None:
    """Retrieve the parser callable associated with the provided suffix."""
    return _PARSER_REGISTRY.get(_normalize_extension(suffix))


def iter_registered_suffixes() -> Iterator[str]:
    """Iterate over all registered parser suffixes."""
    yield from sorted(_PARSER_REGISTRY)
