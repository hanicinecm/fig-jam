"""Shared helper utilities for parser implementations."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from fig_jam.exceptions import DependencyUnavailableError, DiagnosticDetail
from fig_jam.parsers import ParserResult
from fig_jam.utils.mappings import freeze_mapping

_logger = logging.getLogger(__name__)
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


def _read_text(path: Path) -> tuple[str, str, tuple[str, ...]]:
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

    message = "Unable to decode file using supported encodings."
    _logger.debug(
        "Decoding failed for %s",
        path,
        extra={"attempted_encodings": tuple(attempted), "errors": dict(errors)},
    )
    raise _DecodeError(tuple(attempted), errors)


def _decode_and_validate(
    path: Path,
    *,
    format_name: str,
) -> tuple[str, str, tuple[str, ...]] | ParserResult:
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


def _success_result(
    *,
    path: Path,
    format_name: str,
    data: Mapping[str, Any],
    encoding: str,
    attempted_encodings: tuple[str, ...],
) -> ParserResult:
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
        data=freeze_mapping(data),
        diagnostics=diagnostics,
        encoding=encoding,
        success=True,
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
        data=None,
        diagnostics=diagnostics,
        encoding=encoding,
        success=False,
    )


def _dependency_failure_result(
    *,
    path: Path,
    format_name: str,
    dependency: str,
    reason: str | None = None,
    extras: Sequence[str] | None = None,
) -> ParserResult:
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


class _DecodeError(Exception):
    """Raised when no supported encoding can decode the provided bytes."""

    def __init__(self, attempts: Sequence[str], errors: Mapping[str, str]) -> None:
        message = "Unable to decode file using supported encodings."
        super().__init__(message)
        self.attempts = tuple(attempts)
        self.errors = dict(errors)
