"""TOML parser implementation."""

from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - exercised when tomllib missing
    tomllib = None

try:
    import tomli  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    tomli = None


def parse_toml(path: Path) -> dict[str, Any]:
    """Parse a TOML configuration file."""
    ...
