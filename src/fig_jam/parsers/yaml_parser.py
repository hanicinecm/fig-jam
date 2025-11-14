"""YAML parser implementation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fig_jam.parsers import ParserResult, register_parser
from fig_jam.parsers._parsers_utils import (
    _decode_and_validate,
    _dependency_failure_result,
    _failure_result,
    _success_result,
)
from fig_jam.utils.mappings import ensure_mapping

try:
    import yaml  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore[assignment]


def _load_yaml() -> Callable[[str], Any]:
    if yaml is None:  # pragma: no cover - optional dependency
        message = "pyyaml"
        raise ModuleNotFoundError(message)
    return yaml.safe_load


@register_parser(".yaml", ".yml")
def parse_yaml(path: Path) -> ParserResult:
    """Parse a YAML configuration file."""
    decoded = _decode_and_validate(path, format_name="yaml")
    if isinstance(decoded, ParserResult):
        return decoded
    text, encoding, attempted = decoded

    try:
        loader = _load_yaml()
    except ModuleNotFoundError:
        return _dependency_failure_result(
            path=path,
            format_name="yaml",
            dependency="pyyaml",
            reason="YAML parsing requires the optional 'pyyaml' dependency.",
        )

    try:
        parsed = loader(text)
    except Exception as exc:  # noqa: BLE001 - PyYAML raises broad exceptions
        extra = {"error": str(exc)}
        return _failure_result(
            path=path,
            format_name="yaml",
            message="Failed to parse YAML content.",
            encoding=encoding,
            attempted_encodings=attempted,
            extra=extra,
        )

    try:
        mapping = ensure_mapping(parsed)
    except TypeError:
        return _failure_result(
            path=path,
            format_name="yaml",
            message="YAML root object must be a mapping.",
            encoding=encoding,
            attempted_encodings=attempted,
        )

    return _success_result(
        path=path,
        format_name="yaml",
        data=mapping,
        encoding=encoding,
        attempted_encodings=attempted,
    )
