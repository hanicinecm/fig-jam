"""INI/CFG parser implementation."""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Any

from fig_jam.parsers import ParserResult, register_parser
from fig_jam.parsers._parsers_utils import (
    _decode_and_validate,
    _failure_result,
    _success_result,
)
from fig_jam.utils.mappings import freeze_mapping


@register_parser(".ini", ".cfg")
def parse_ini(path: Path) -> ParserResult:
    """Parse an INI or CFG configuration file."""
    decoded = _decode_and_validate(path, format_name="ini")
    if isinstance(decoded, ParserResult):
        return decoded
    text, encoding, attempted = decoded

    parser = configparser.ConfigParser()
    parser.optionxform = str  # type: ignore[assignment] # preserve key casing

    try:
        parser.read_string(text)
    except configparser.Error as exc:
        extra = {"error": str(exc)}
        return _failure_result(
            path=path,
            format_name="ini",
            message="Failed to parse INI content.",
            encoding=encoding,
            attempted_encodings=attempted,
            extra=extra,
        )

    data: dict[str, Any] = {}
    if parser.defaults():
        data["DEFAULT"] = dict(parser.defaults())
    for section in parser.sections():
        data[section] = dict(parser.items(section))

    mapping = freeze_mapping(data)
    return _success_result(
        path=path,
        format_name="ini",
        data=mapping,
        encoding=encoding,
        attempted_encodings=attempted,
    )
