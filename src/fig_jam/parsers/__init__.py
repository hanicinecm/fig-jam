"""Parser registry and public interfaces for fig_jam parsers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fig_jam.exceptions import DiagnosticDetail
from fig_jam.utils.mappings import freeze_mapping
from fig_jam.utils.paths import normalize_extension

__all__ = [
    "ParserCallable",
    "ParserResult",
    "get_registered_parser",
    "iter_registered_suffixes",
    "register_parser",
]

ParserCallable = Callable[[Path], "ParserResult"]
ExtensionArg = str | Iterable[str]

_PARSER_REGISTRY: dict[str, ParserCallable] = {}


@dataclass(frozen=True)
class ParserResult:
    """Represents the outcome of attempting to parse a configuration file."""

    data: Mapping[str, Any] | None
    diagnostics: tuple[DiagnosticDetail, ...]
    encoding: str | None
    success: bool

    def __post_init__(self) -> None:
        """Ensure mapping payloads remain immutable for downstream consumers."""
        if self.data is not None and isinstance(self.data, Mapping):
            object.__setattr__(self, "data", freeze_mapping(self.data))


def register_parser(
    *extensions: ExtensionArg,
) -> Callable[[ParserCallable], ParserCallable]:
    """Register a parser callable for one or more file extensions."""
    if not extensions:
        msg = "At least one extension must be provided."
        raise ValueError(msg)

    normalized_extensions: tuple[str, ...] = tuple(
        normalize_extension(ext) for ext in _flatten_extensions(extensions)
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


def get_registered_parser(suffix: str) -> ParserCallable | None:
    """Retrieve the parser callable associated with the provided suffix."""
    return _PARSER_REGISTRY.get(normalize_extension(suffix))


def iter_registered_suffixes() -> Iterator[str]:
    """Iterate over all registered parser suffixes."""
    yield from sorted(_PARSER_REGISTRY)


def _flatten_extensions(raw_extensions: Iterable[ExtensionArg]) -> Iterator[str]:
    for raw in raw_extensions:
        if isinstance(raw, str):
            yield raw
        else:
            yield from raw
