"""JSON parser implementation."""

from __future__ import annotations

import json
from pathlib import Path

from fig_jam.parsers import (
    ParserResult,
    _decode_and_validate,
    _failure_result,
    _success_result,
    register_parser,
)
from fig_jam.utils.mappings import ensure_mapping


@register_parser(".json")
def parse_json(path: Path) -> ParserResult:
    """Parse a JSON configuration file."""
    decoded = _decode_and_validate(path, format_name="json")
    if isinstance(decoded, ParserResult):
        return decoded

    text, encoding, attempted = decoded
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        extra = {"error": exc.msg, "lineno": exc.lineno, "colno": exc.colno}
        return _failure_result(
            path=path,
            format_name="json",
            message="Failed to parse JSON content.",
            encoding=encoding,
            attempted_encodings=attempted,
            extra=extra,
        )

    try:
        mapping = ensure_mapping(parsed)
    except TypeError:
        return _failure_result(
            path=path,
            format_name="json",
            message="JSON root object must be a mapping.",
            encoding=encoding,
            attempted_encodings=attempted,
        )

    return _success_result(
        path=path,
        format_name="json",
        data=mapping,
        encoding=encoding,
        attempted_encodings=attempted,
    )
