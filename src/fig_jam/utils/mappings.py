"""Utility helpers for working with mapping data structures."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def freeze_mapping(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return an immutable shallow copy of the mapping.

    Args:
        data: Mapping produced by an upstream stage.

    Returns:
        Mapping proxy that prevents downstream mutation.
    """
    if isinstance(data, MappingProxyType):
        return data
    return MappingProxyType(dict(data))


def ensure_mapping(value: Any) -> Mapping[str, Any]:
    """Validate that the supplied value is a mapping and return it immutably.

    Args:
        value: Parsed object returned by a decoder or intermediate stage.

    Returns:
        Mapping proxy representing the configuration root.

    Raises:
        TypeError: If the value is not a mapping.
    """
    if not isinstance(value, Mapping):
        message = "Parsed data must be a mapping."
        raise TypeError(message)
    return freeze_mapping(value)
