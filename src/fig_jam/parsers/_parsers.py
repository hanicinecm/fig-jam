"""Parser implementations and registry for fig_jam."""

from __future__ import annotations

import configparser
import json
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from fig_jam.parsers._parsers_errors import (
    ParserDependencyError,
    ParserSyntaxError,
)
from fig_jam.parsers._parsers_utils import parse_mapping, read_text

try:
    import tomllib  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - exercised when tomllib missing
    tomllib = None

try:
    import tomli  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    tomli = None

try:
    import yaml  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    yaml = None


Parser = Callable[[Path], dict[str, Any]]

PARSER_REGISTRY: dict[str, Parser] = {}


def iter_supported_suffixes() -> Iterator[str]:
    """Iterate over all registered parser suffixes."""
    yield from PARSER_REGISTRY.keys()


def get_parser(suffix: str) -> Parser:
    """Parse a configuration file based on its suffix."""
    if suffix not in PARSER_REGISTRY:
        message = f"No parser registered for suffix: {suffix!r}"
        raise ValueError(message)
    return PARSER_REGISTRY[suffix]


def register_parser(*suffixes: str) -> Callable[[Parser], Parser]:
    """Register a parser for one or more suffixes.

    Args:
        *suffixes: One or more suffixes to register the parser for.

    Returns:
        A decorator that registers the parser function.

    Raises:
        ValueError: When a parser is already registered for a suffix.
        ValueError: When the suffix is not well-formed.
    """
    suffix_pattern = re.compile(r"^\.[a-zA-Z0-9]+$")
    if any(not suffix_pattern.match(suffix) for suffix in suffixes):
        msg = "Suffixes must start with a dot and contain only alphanumeric characters."
        raise ValueError(msg)
    if any(suffix in PARSER_REGISTRY for suffix in suffixes):
        msg = "A parser is already registered for one or more of the given suffixes."
        raise ValueError(msg)

    def decorator(func: Parser) -> Parser:
        for suffix in suffixes:
            PARSER_REGISTRY[suffix] = func
        return func

    return decorator


@register_parser(".ini", ".cfg")
def _parse_ini(path: Path) -> dict[str, Any]:
    """Parse an INI or CFG configuration file.

    Args:
        path: Location of the INI or CFG file.

    Returns:
        Parsed payload as a mapping of sections to option maps.

    Raises:
        ParserSyntaxError: When the INI file contains invalid syntax.
    """
    parser = configparser.ConfigParser()
    parser.optionxform = lambda optionstr: optionstr
    raw = read_text(path)
    try:
        parser.read_string(raw)
    except configparser.Error as exc:
        raise ParserSyntaxError(path, exc) from exc
    payload: dict[str, Any] = {
        section: dict(parser[section]) for section in parser.sections()
    }
    defaults = dict(parser.defaults())
    if defaults:
        payload[parser.default_section] = defaults
    return payload


@register_parser(".json")
def _parse_json(path: Path) -> dict[str, Any]:
    """Parse a JSON configuration file.

    Args:
        path: Location of the JSON file to decode.

    Returns:
        Parsed payload as a mapping.

    Raises:
        ParserSyntaxError: When the JSON file is malformed.
        ParserTypeError: When the parsed data is not a mapping.
    """
    return parse_mapping(path, json.loads)


@register_parser(".toml")
def _parse_toml(path: Path) -> dict[str, Any]:
    """Parse a TOML configuration file.

    Args:
        path: Location of the TOML file.

    Returns:
        Parsed payload as a mapping.

    Raises:
        ParserDependencyError: When neither tomllib nor tomli is available.
    """
    loader = None
    if tomllib is not None:
        loader = tomllib.loads
    if tomli is not None:
        loader = tomli.loads
    if loader is None:
        missing_dependency = "tomli"
        hint = "Install it with `uv add tomli` or `pip install tomli`."
        raise ParserDependencyError(missing_dependency, hint)
    return parse_mapping(path, loader)


@register_parser(".yaml", ".yml")
def _parse_yaml(path: Path) -> dict[str, Any]:
    """Parse a YAML configuration file.

    Args:
        path: Location of the YAML file.

    Returns:
        Parsed payload as a mapping.

    Raises:
        ParserDependencyError: When PyYAML is not installed.
    """
    if yaml is None:
        dependency = "pyyaml"
        hint = "Install it with `uv add pyyaml` or `pip install pyyaml`."
        raise ParserDependencyError(dependency, hint)
    return parse_mapping(path, yaml.safe_load)
