"""TOML parser implementation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from fig_jam.parsers import (
    ParserResult,
    _decode_and_validate,
    _dependency_failure_result,
    _failure_result,
    _success_result,
    register_parser,
)
from fig_jam.utils.mappings import ensure_mapping

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised when tomllib missing
    tomllib = None  # type: ignore[assignment]

try:
    import tomli  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    tomli = None  # type: ignore[assignment]


def _load_toml() -> Callable[[str], Mapping[str, Any]]:
    if tomllib is not None:
        return tomllib.loads
    if tomli is None:  # pragma: no cover - optional dependency
        message = "tomli"
        raise ModuleNotFoundError(message)
    return tomli.loads


@register_parser(".toml")
def parse_toml(path: Path) -> ParserResult:
    """Parse a TOML configuration file."""
    decoded = _decode_and_validate(path, format_name="toml")
    if isinstance(decoded, ParserResult):
        return decoded
    text, encoding, attempted = decoded

    try:
        loader = _load_toml()
    except ModuleNotFoundError:
        return _dependency_failure_result(
            path=path,
            format_name="toml",
            dependency="tomli",
            reason="TOML parsing requires either Python 3.11+ or the 'tomli' package.",
            extras=("tomli",),
        )

    try:
        parsed = loader(text)
    except (ValueError, TypeError) as exc:
        extra = {"error": str(exc)}
        return _failure_result(
            path=path,
            format_name="toml",
            message="Failed to parse TOML content.",
            encoding=encoding,
            attempted_encodings=attempted,
            extra=extra,
        )

    try:
        mapping = ensure_mapping(parsed)
    except TypeError:
        return _failure_result(
            path=path,
            format_name="toml",
            message="TOML root object must be a mapping.",
            encoding=encoding,
            attempted_encodings=attempted,
        )

    return _success_result(
        path=path,
        format_name="toml",
        data=mapping,
        encoding=encoding,
        attempted_encodings=attempted,
    )
