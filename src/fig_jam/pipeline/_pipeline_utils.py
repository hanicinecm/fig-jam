"""Shared helpers used across the fig_jam pipeline stages."""

from __future__ import annotations

import dataclasses
import types
from collections.abc import Iterator, MutableMapping
from typing import Annotated, Any, Union, get_args, get_origin

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - optional dependency
    BaseModel = None

UnionType = getattr(types, "UnionType", None)


def is_dataclass_type(value: Any) -> bool:
    """Determine whether the provided value is a dataclass type."""
    return isinstance(value, type) and dataclasses.is_dataclass(value)


def is_pydantic_model_type(value: Any) -> bool:
    """Return True when the object is a subclass of BaseModel."""
    if BaseModel is None or not isinstance(value, type):
        return False
    return issubclass(value, BaseModel)


def get_model_validator_type(value: Any) -> type[Any] | None:
    """Return the validator type when it is a dataclass or BaseModel."""
    if is_dataclass_type(value) or is_pydantic_model_type(value):
        return value
    return None


def iter_model_fields(model_type: type) -> Iterator[tuple[str, Any]]:
    """Yield field names and annotations for dataclasses and BaseModels.

    Args:
        model_type: Validator type inspected for fields.

    Yields:
        Tuples of field name and its annotation.

    Raises:
        TypeError: When the provided model type is not supported.
    """
    if is_dataclass_type(model_type):
        for field in dataclasses.fields(model_type):
            yield field.name, field.type
        return
    if is_pydantic_model_type(model_type):
        model_fields = getattr(model_type, "model_fields", None)
        if model_fields is not None:
            for name, info in model_fields.items():
                annotation = getattr(info, "annotation", None)
                yield name, annotation
            return
        legacy_fields = getattr(model_type, "__fields__", {})
        for name, info in legacy_fields.items():
            annotation = getattr(info, "annotation", None)
            yield name, annotation

    message = f"unsupported model type: {model_type!r}"
    raise TypeError(message)


def collect_env_override_paths(model_type: type | None) -> dict[tuple[str, ...], str]:
    """Collect override mappings for a validator hierarchy.

    Args:
        model_type: Root validator type that may declare `__env_overrides__`.

    Returns:
        Mapping from dotted validator field paths to environment variable names.
    """
    overrides: dict[tuple[str, ...], str] = {}
    if model_type is None:
        return overrides

    visited: set[type] = set()

    def _walk(current_type: type, prefix: tuple[str, ...]) -> None:
        if current_type in visited:
            return
        visited.add(current_type)
        mapping = getattr(current_type, "__env_overrides__", None)
        if isinstance(mapping, dict):
            for field_name, env_var in mapping.items():
                overrides[(*prefix, field_name)] = env_var
        for field_name, annotation in iter_model_fields(current_type):
            nested = _resolve_model_type(annotation)
            if nested is None:
                continue
            _walk(nested, (*prefix, field_name))

    _walk(model_type, ())
    return overrides


def _resolve_model_type(hint: Any) -> type | None:
    """Resolve a validator type from the provided annotation hint.

    Args:
        hint: Annotation that may reference nested dataclasses or Pydantic
            models.

    Returns:
        The validator type referenced by `hint` or `None` when no such type
        exists.
    """
    if isinstance(hint, type):
        if is_dataclass_type(hint) or is_pydantic_model_type(hint):
            return hint
        return None
    origin = get_origin(hint)
    if origin is Annotated:
        args = get_args(hint)
        if not args:
            return None
        return _resolve_model_type(args[0])
    if origin is Union or origin is UnionType:
        for arg in get_args(hint):
            if arg is type(None):
                continue
            nested = _resolve_model_type(arg)
            if nested is not None:
                return nested
    return None


def apply_nested_override(
    payload: MutableMapping[str, Any], path: tuple[str, ...], value: str
) -> bool:
    """Insert a value into the payload using the dotted path index.

    Args:
        payload: Mutable mapping representing the current validator payload.
        path: Sequence of keys describing the nested location to override.
        value: Environment-provided value applied to the final key.

    Returns:
        `True` when the override was written, otherwise `False` if the path
        could not be traversed or the terminal key was missing.
    """
    node: MutableMapping[str, Any] = payload
    for segment in path[:-1]:
        next_node = node.get(segment)
        if not isinstance(next_node, MutableMapping):
            return False
        node = next_node
    final_key = path[-1]
    if final_key not in node:
        return False
    node[final_key] = value
    return True


def is_list_validator(value: Any) -> bool:
    """Check whether the validator describes a list of keys.

    Args:
        value: Validator supplied by the user.

    Returns:
        `True` when the validator is a list of strings, otherwise `False`.
    """
    if not isinstance(value, list):
        return False
    return all(isinstance(entry, str) for entry in value)


def is_dict_validator(value: Any) -> bool:
    """Check whether the validator describes a dict of key→type pairs.

    Args:
        value: Validator supplied by the user.

    Returns:
        `True` when the validator is a dict that maps strings to types,
        otherwise `False`.
    """
    if not isinstance(value, dict):
        return False
    return all(
        isinstance(key, str) and isinstance(validator_type, type)
        for key, validator_type in value.items()
    )
