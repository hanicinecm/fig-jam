"""Parser registry and built-in parsers for supported configuration files.

The module defines the suffix-to-parser registry (`PARSER_REGISTRY`) that
configuration discovery code inspects, along with every builtin parser
implementation for INI, JSON, TOML, and YAML. It also encapsulates dependency
checks and loader normalization so callers outside this package do not need to
handle format-specific exceptions.

The module exposes two public functions for querying the registry:
`get_parser` and `iter_supported_suffixes`.
"""

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

__all__ = ["get_parser", "iter_supported_suffixes"]


Parser = Callable[[Path], dict[str, Any]]

PARSER_REGISTRY: dict[str, Parser] = {}


def iter_supported_suffixes() -> Iterator[str]:
    """Iterate through every suffix with a registered parser.

    The iterator can be consumed by discovery stages that need to
    enumerate the supported extensions without knowing which parsers are
    actually available at runtime.

    Returns:
        An iterator over every registered suffix. Each suffix starts with a dot.
    """
    yield from PARSER_REGISTRY.keys()


def get_parser(suffix: str) -> Parser:
    """Return the parser callable associated with the suffix.

    The parser returned is a callable that accepts a `Path` and returns
    a dictionary representing the parsed configuration file.
    If the file under the path cannot be parsed, the callable raises one of the
    parser errors (subclasses of the `ParserError` base class).

    Args:
        suffix: The suffix to look up, starting with a dot.

    Returns:
        The parser callable registered for the suffix.

    Raises:
        ValueError: When no parser is registered for the suffix.
    """
    if suffix not in PARSER_REGISTRY:
        message = f"No parser registered for suffix: {suffix!r}"
        raise ValueError(message)
    return PARSER_REGISTRY[suffix]


def register_parser(*suffixes: str) -> Callable[[Parser], Parser]:
    """Register a parser for one or more suffixes ensuring they are valid.

    The decorator enforces a naming pattern (a dot followed by alphanumeric
    characters) and guards against overriding already-registered suffixes.
    Each suffix is mapped to a single callable, so the first registration
    wins and subsequent attempts raise to prevent ambiguity.

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
    """Parse INI and CFG files while honoring case and defaults.

    ConfigParser is configured to preserve option and section casing, and both
    section data and the implicit DEFAULT section are copied into a mapping
    so callers can reason about every available entry.

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
    """Parse a JSON configuration file into a mapping.

    JSON source files are decoded through `parse_mapping` so syntax errors are
    normalized to `ParserSyntaxError` and the loader ensures a mapping is
    returned before any downstream code reads the configuration.

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
    """Parse a TOML configuration file using the available loader.

    The function detects whether the stdlib `tomllib` is available and falls
    back to `tomli` when running on older Python versions. If neither loader
    is installed, a `ParserDependencyError` explains how to resolve the
    dependency so that config discovery can proceed.

    Args:
        path: Location of the TOML file.

    Returns:
        Parsed payload as a mapping.

    Raises:
        ParserDependencyError: When neither tomllib nor tomli is available.
        ParserSyntaxError: When the TOML file is malformed.
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
    """Parse a YAML configuration file through PyYAML's safe loader.

    YAML parsing relies on PyYAML being installed and uses `yaml.safe_load`
    to avoid executing arbitrary constructors while still producing native
    Python structures. If the dependency is missing, a parser dependency error
    points the caller at the installation instructions.

    Args:
        path: Location of the YAML file.

    Returns:
        Parsed payload as a mapping.

    Raises:
        ParserDependencyError: When PyYAML is not installed.
        ParserSyntaxError: When the YAML file is malformed.
        ParserTypeError: When the parsed data is not a mapping.
    """
    if yaml is None:
        dependency = "pyyaml"
        hint = "Install it with `uv add pyyaml` or `pip install pyyaml`."
        raise ParserDependencyError(dependency, hint)
    return parse_mapping(path, yaml.safe_load)
