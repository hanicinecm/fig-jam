"""Environment variable overrides for fig_jam."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def apply_overrides(
    data: Mapping[str, Any],
    *,
    section: str | None,
    environment: Mapping[str, str] | None = None,
) -> Mapping[str, Any]:
    """Apply FIG_JAM environment overrides to the supplied mapping."""
    message = "Override handling will be implemented in Task 4."
    raise NotImplementedError(message)
