"""Cache management for fig_jam configuration loads."""

from __future__ import annotations

import copy
import inspect
import threading
from collections.abc import Callable, Mapping, Sequence
from functools import wraps
from pathlib import Path
from types import MappingProxyType
from typing import Any

_CACHE_CLEARERS: list[Callable[[], None]] = []
_SEQUENCE_EXCLUSIONS = (str, bytes, bytearray)


def cached_loader(func: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a loader callable with caching behaviour."""
    signature = inspect.signature(func)
    cache: dict[Any, Any] = {}
    lock = threading.RLock()

    def clear() -> None:
        with lock:
            cache.clear()

    _CACHE_CLEARERS.append(clear)

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()

        key = _make_cache_key(
            path=bound.arguments.get("canonical_path"),
            section=bound.arguments.get("section"),
            validator=bound.arguments.get("validator"),
            enable_overrides=bound.arguments.get("enable_overrides", False),
            override_signature=bound.arguments.get("override_signature"),
        )

        if key is not None:
            with lock:
                cached = cache.get(key)
            if cached is not None:
                return _clone_result(cached)

        result = func(*args, **kwargs)

        if key is None:
            return _clone_result(result)

        snapshot = _clone_result(result)
        with lock:
            cache[key] = snapshot
        return _clone_result(snapshot)

    return wrapper


def clear_cache() -> None:
    """Clear cached configuration results."""
    for clear in _CACHE_CLEARERS:
        clear()


def _make_cache_key(
    *,
    path: Any,
    section: str | None,
    validator: Any,
    enable_overrides: bool,
    override_signature: Any,
) -> tuple[Any, ...] | None:
    """Construct a cache key or return ``None`` if caching should be bypassed."""
    path_key = _normalize_path_key(path)
    validator_key = _normalize_validator_key(validator)
    if validator_key is None:
        return None
    overrides_key = tuple(override_signature or ())
    return (path_key, section, validator_key, enable_overrides, overrides_key)


def _normalize_path_key(path: Any) -> str:
    """Normalise a path argument into a canonical string."""
    if isinstance(path, Path):
        return str(path)
    if isinstance(path, str):
        return path
    return str(path)


def _normalize_validator_key(validator: Any) -> tuple[Any, ...] | None:
    """Derive a hashable identity for the supplied validator."""
    result: tuple[Any, ...] | None = None

    if validator is None:
        result = ("none",)
    elif isinstance(validator, Mapping):
        items: list[tuple[str, tuple[str, str]]] = []
        for key, value in sorted(validator.items(), key=lambda item: item[0]):
            if not isinstance(key, str) or not isinstance(value, type):
                return None
            items.append((key, (value.__module__, value.__qualname__)))
        result = ("mapping", tuple(items))
    elif isinstance(validator, Sequence) and not isinstance(
        validator,
        _SEQUENCE_EXCLUSIONS,
    ):
        if not all(isinstance(item, str) for item in validator):
            return None
        result = ("sequence", tuple(validator))
    elif isinstance(validator, type):
        result = ("type", validator.__module__, validator.__qualname__)

    return result


def _clone_result(value: Any) -> Any:
    """Return a safe copy of a cached value."""
    if isinstance(value, MappingProxyType):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    try:
        return copy.deepcopy(value)
    except (TypeError, copy.Error):  # pragma: no cover - extremely defensive
        return value
