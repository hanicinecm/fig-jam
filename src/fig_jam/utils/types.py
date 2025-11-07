"""Type coercion utilities shared across validation routines."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union, get_args, get_origin


def coerce_bool_value(value: Any) -> bool:
    """Coerce a value into a boolean using human-friendly rules."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        message = "Cannot coerce string value to bool."
        raise TypeError(message)
    if isinstance(value, (int, float)):
        return bool(value)
    message = "Cannot coerce value to bool."
    raise TypeError(message)


def coerce_value(value: Any, target_type: type) -> Any:
    """Coerce a value to the target type with helpful error messaging."""
    if isinstance(value, target_type):
        return value

    if target_type is bool:
        return coerce_bool_value(value)

    if target_type is Path:
        if isinstance(value, (str, Path)):
            return target_type(value)
        message = "Cannot coerce value to Path."
        raise TypeError(message)

    if target_type in {int, float, str}:
        return target_type(value)

    return target_type(value)


def coerce_for_annotation(value: Any, annotation: Any) -> Any:
    """Coerce a value according to a type annotation."""
    origin = get_origin(annotation)
    if origin is None:
        if annotation in {Any, object} or annotation is None:
            return value
        if isinstance(annotation, type):
            return coerce_value(value, annotation)
        return value

    if origin is Union:
        args = get_args(annotation)
        if type(None) in args and value is None:
            return None
        for arg in args:
            if arg is type(None):
                continue
            try:
                return coerce_for_annotation(value, arg)
            except (TypeError, ValueError):
                continue
        message = "Value does not match any allowed Union variant."
        raise ValueError(message)

    return value


def describe_annotation(annotation: Any) -> str:
    """Return a human-readable description of a type annotation."""
    origin = get_origin(annotation)
    if origin is None:
        return getattr(annotation, "__name__", str(annotation))

    if origin is Union:
        parts = ", ".join(describe_annotation(arg) for arg in get_args(annotation))
        return f"Union[{parts}]"

    return str(annotation)
