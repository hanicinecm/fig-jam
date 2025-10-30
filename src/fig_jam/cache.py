"""Cache management for fig_jam configuration loads."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def cached_loader(func: Callable[..., Any]) -> Callable[..., Any]:
    """Create a cached loader wrapper for configuration loads."""
    message = "Caching will be implemented in Task 6."
    raise NotImplementedError(message)


def clear_cache() -> None:
    """Clear cached configuration results."""
    message = "Cache clearing will be implemented in Task 6."
    raise NotImplementedError(message)
