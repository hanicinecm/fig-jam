"""Top-level configuration loader orchestration for fig_jam."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def get_config(
    path: Path | None = None,
    section: str | None = None,
    validator: Any | None = None,
    *,
    enable_overrides: bool = False,
) -> Any:
    """Load configuration data according to the provided parameters."""
    message = "Loader implementation will be provided in Task 7."
    raise NotImplementedError(message)


def _load_config_internal(
    path: Path | None,
    section: str | None,
    validator: Any | None,
    *,
    enable_overrides: bool,
) -> Any:
    """Run the configuration pipeline stages in order."""
    message = "Loader orchestration will be provided in Task 7."
    raise NotImplementedError(message)
