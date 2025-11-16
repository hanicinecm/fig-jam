"""Parser registry and public interfaces for fig_jam parsers."""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from fig_jam.parsers.ini_parser import parse_ini
from fig_jam.parsers.json_parser import parse_json
from fig_jam.parsers.toml_parser import parse_toml
from fig_jam.parsers.yaml_parser import parse_yaml

Parser = Callable[[Path], dict[str, Any]]

_PARSER_REGISTRY: dict[str, Parser] = {
    ".ini": parse_ini,
    ".cfg": parse_ini,
    ".json": parse_json,
    ".toml": parse_toml,
    ".yaml": parse_yaml,
    ".yml": parse_yaml,
}


def iter_supported_suffixes() -> Iterator[str]:
    """Iterate over all registered parser suffixes."""
    yield from _PARSER_REGISTRY.keys()


def get_parser(suffix: str) -> Parser:
    """Parse a configuration file based on its suffix."""
    if suffix not in _PARSER_REGISTRY:
        message = f"No parser registered for suffix: {suffix!r}"
        raise ValueError(message)
    return _PARSER_REGISTRY[suffix]
