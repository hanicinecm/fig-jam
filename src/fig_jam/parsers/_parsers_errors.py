"""Parser-specific error hierarchy for fig_jam."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


class ParserError(Exception):
    """Base class for errors raised by parser implementations."""


class ParserDependencyError(ParserError, ModuleNotFoundError):
    """Raised when a parser cannot run because a dependency is missing.

    Args:
        dependency: Name of the missing module.
        hint: Explanation of how to resolve the missing dependency.
    """

    def __init__(self, dependency: str, hint: str) -> None:
        """Record the missing dependency and the resolution hint."""
        self.dependency = dependency
        message = (
            f"{dependency} is required to parse this configuration. {hint} "
            "This is an internal parser exception; if you see it, something went wrong."
        )
        super().__init__(message)


class ParserDecodingError(ParserError, UnicodeError):
    """Raised when supported encodings cannot decode a configuration file.

    Args:
        path: Location of the file that could not be decoded.
        attempted_encodings: Encodings that were tried in order.
    """

    def __init__(self, path: Path, attempted_encodings: Sequence[str]) -> None:
        """Record the path and the encodings that were tried."""
        self.path = path
        self.attempted_encodings = tuple(attempted_encodings)
        joined = ", ".join(self.attempted_encodings)
        message = (
            f"Could not decode {path} using any of: {joined}. "
            "This is an internal parser exception; if you see it, something went wrong."
        )
        super().__init__(message)


class ParserSyntaxError(ParserError, ValueError):
    """Raised when the parser encounters invalid syntax.

    Args:
        path: Location of the file that failed to parse.
        error: Underlying exception describing the syntax issue.
    """

    def __init__(self, path: Path, error: Exception) -> None:
        """Record the path and the underlying syntax failure."""
        self.path = path
        self.error = error
        message = (
            f"Failed to parse {path}: {error}. "
            "This is an internal parser exception; if you see it, something went wrong."
        )
        super().__init__(message)


class ParserTypeError(ParserError, TypeError):
    """Raised when parsed content is not a mapping.

    Args:
        path: Source file of the invalid data.
        actual_type: Type returned by the parser.
    """

    def __init__(self, path: Path, actual_type: type) -> None:
        """Record the path and the unexpected return type."""
        self.path = path
        self.actual_type = actual_type
        message = (
            f"Parser for {path} returned {actual_type.__name__}; expected a mapping. "
            "This is an internal parser exception; if you see it, something went wrong."
        )
        super().__init__(message)
