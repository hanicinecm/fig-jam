"""Parser-specific error hierarchy for fig_jam.

This module exposes the exceptions raised by the builtin
parsers, allowing the higher-level loader to catch and report consistent error
types without binding to individual parsing libraries.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


class ParserError(Exception):
    """Base class for errors raised by parser implementations.

    Parser-specific exceptions inherit from this class so the loader can
    catch parser failures without being tied to a concrete format or failure
    type.
    """


class ParserDependencyError(ParserError, ModuleNotFoundError):
    """Raised when a parser cannot run because a dependency is missing.

    The exception message includes guidance so callers can install the
    missing module and resume parsing without further dependency checks.

    Args:
        dependency: Name of the missing module.
        hint: Explanation of how to resolve the missing dependency.
    """

    def __init__(self, dependency: str, hint: str) -> None:
        """Record the missing dependency and the resolution hint."""
        self.dependency = dependency
        self.hint = hint
        message = (
            f"{dependency} is required to parse this configuration. {hint} "
            "This is an internal parser exception; if you see it, something went wrong."
        )
        super().__init__(message)


class ParserDecodingError(ParserError, UnicodeError):
    """Raised when supported encodings cannot decode a configuration file.

    The raised exception enumerates the encodings that were attempted so
    callers can log or surface exactly why decoding failed before escalating.

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

    Syntax errors are wrapped and re-raised so higher layers can surface a
    consistent failure without depending on the loader's native exception
    types.

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

    This guards the contract expected by the loader pipeline, which always
    operates on mappings regardless of the serialization format.

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
