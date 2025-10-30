"""Parser registry and format-specific parser interfaces for fig_jam."""

from __future__ import annotations

import configparser
import json
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fig_jam.exceptions import DependencyUnavailableError, DiagnosticDetail

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised when tomllib missing
    tomllib = None  # type: ignore[assignment]

try:
    import tomli  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    tomli = None  # type: ignore[assignment]

try:
    import yaml  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore[assignment]

ParserCallable = Callable[[Path], "ParserResult"]
ExtensionArg = str | Iterable[str]

_PARSER_REGISTRY: dict[str, ParserCallable] = {}
_TEXT_ENCODINGS: tuple[str, ...] = (
    "utf-8",
    "utf-8-sig",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "utf-32",
    "utf-32-le",
    "utf-32-be",
    "ascii",
    "latin-1",
    "cp1252",
)


@dataclass(frozen=True)
class ParserResult:
    """Represents the outcome of attempting to parse a configuration file."""

    data: Mapping[str, Any] | None
    diagnostics: tuple[DiagnosticDetail, ...]
    encoding: str | None
    success: bool


class _DecodeError(Exception):
    """Raised when no supported encoding can decode the provided bytes."""

    def __init__(self, attempts: Sequence[str], errors: Mapping[str, str]) -> None:
        """Record attempted encodings and failure reasons."""
        message = "Unable to decode file using supported encodings."
        super().__init__(message)
        self.attempts = tuple(attempts)
        self.errors = MappingProxyType(dict(errors))


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


def _read_text(path: Path) -> tuple[str, str, tuple[str, ...]]:
    """Read file bytes and decode using a suite of fallback encodings."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        message = f"Failed to read file: {exc.strerror or exc}"
        raise OSError(message) from exc

    attempted: list[str] = []
    errors: dict[str, str] = {}
    for encoding in _TEXT_ENCODINGS:
        attempted.append(encoding)
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError as exc:
            reason = f"{exc.reason} at position {exc.start}"
            errors[encoding] = reason
        else:
            return text, encoding, tuple(attempted)

    raise _DecodeError(attempted, errors)


def _freeze_mapping(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return an immutable shallow copy of the mapping."""
    if isinstance(data, MappingProxyType):
        return data
    return MappingProxyType(dict(data))


def _ensure_mapping(value: Any) -> Mapping[str, Any]:
    """Validate that the parsed root object is a mapping."""
    if not isinstance(value, Mapping):
        message = "Parsed data must be a mapping."
        raise TypeError(message)
    return _freeze_mapping(value)


def _success_result(
    *,
    path: Path,
    format_name: str,
    data: Mapping[str, Any],
    encoding: str,
    attempted_encodings: tuple[str, ...],
) -> ParserResult:
    """Construct a successful parser result with diagnostics."""
    diagnostics = (
        DiagnosticDetail(
            stage=f"parsers.{format_name}",
            message="Parsed configuration successfully.",
            data={
                "path": str(path),
                "format": format_name,
                "encoding": encoding,
                "attempted_encodings": attempted_encodings,
            },
        ),
    )
    return ParserResult(
        data=data, diagnostics=diagnostics, encoding=encoding, success=True
    )


def _failure_result(
    *,
    path: Path,
    format_name: str,
    message: str,
    encoding: str | None = None,
    attempted_encodings: tuple[str, ...] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> ParserResult:
    """Construct a failed parser result with diagnostics."""
    payload: dict[str, Any] = {"path": str(path), "format": format_name}
    if encoding is not None:
        payload["encoding"] = encoding
    if attempted_encodings is not None:
        payload["attempted_encodings"] = attempted_encodings
    if extra:
        payload.update(extra)

    diagnostics = (
        DiagnosticDetail(
            stage=f"parsers.{format_name}",
            message=message,
            data=payload,
        ),
    )
    return ParserResult(
        data=None, diagnostics=diagnostics, encoding=encoding, success=False
    )


def _dependency_failure_result(
    *,
    path: Path,
    format_name: str,
    dependency: str,
    reason: str | None = None,
    extras: Sequence[str] | None = None,
) -> ParserResult:
    """Create a failure result capturing missing dependency remediation guidance."""
    error = DependencyUnavailableError(
        dependency,
        reason=reason,
        extras=extras,
    )
    remediation = [hint.as_dict() for hint in error.remediation]
    extra: dict[str, Any] = {
        "dependency": dependency,
        "remediation": remediation,
    }
    if extras:
        extra["extras"] = tuple(extras)
    if reason:
        extra["reason"] = reason
    return _failure_result(
        path=path,
        format_name=format_name,
        message=error.summary,
        extra=extra,
    )


def _decode_and_validate(
    path: Path, *, format_name: str
) -> tuple[str, str, tuple[str, ...]] | ParserResult:
    """Decode a text configuration file, returning early failure results if needed."""
    try:
        text, encoding, attempted = _read_text(path)
    except _DecodeError as exc:
        return _failure_result(
            path=path,
            format_name=format_name,
            message="Unable to decode file with supported encodings.",
            attempted_encodings=exc.attempts,
            extra={"decoding_errors": dict(exc.errors)},
        )
    except OSError as exc:
        return _failure_result(
            path=path,
            format_name=format_name,
            message=str(exc),
        )
    return text, encoding, attempted


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
        extra = {
            "error": exc.msg,
            "lineno": exc.lineno,
            "colno": exc.colno,
        }
        return _failure_result(
            path=path,
            format_name="json",
            message="Failed to parse JSON content.",
            encoding=encoding,
            attempted_encodings=attempted,
            extra=extra,
        )

    try:
        mapping = _ensure_mapping(parsed)
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


def _load_toml() -> Callable[[str], Mapping[str, Any]]:
    """Return a TOML loader callable."""
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
        mapping = _ensure_mapping(parsed)
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


@register_parser(".ini", ".cfg")
def parse_ini(path: Path) -> ParserResult:
    """Parse an INI/CFG configuration file."""
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

    mapping = _freeze_mapping(data)
    return _success_result(
        path=path,
        format_name="ini",
        data=mapping,
        encoding=encoding,
        attempted_encodings=attempted,
    )


def _load_yaml() -> Callable[[str], Any]:
    """Return the YAML loader function."""
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
        mapping = _ensure_mapping(parsed)
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
