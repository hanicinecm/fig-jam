"""Expose the public entry points for the fig_jam package.

This module forms the outward-facing contract of the library. It re-exports
the loader entry point and user-visible exception types defined in sibling
modules.
"""

from __future__ import annotations

from fig_jam.exceptions import (
    ConfigSourceAmbiguityError,
    ConfigSourceNotFoundError,
    ConfigValidationError,
)
from fig_jam.loader import get_config

__all__ = [
    "ConfigSourceAmbiguityError",
    "ConfigSourceNotFoundError",
    "ConfigValidationError",
    "get_config",
]
