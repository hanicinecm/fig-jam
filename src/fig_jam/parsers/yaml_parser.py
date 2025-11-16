"""YAML parser implementation."""

from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    yaml = None


def parse_yaml(path: Path) -> dict[str, Any]:
    """Parse a YAML configuration file."""
    ...
