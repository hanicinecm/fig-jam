"""Helpers for validator inspection."""

from __future__ import annotations

import dataclasses
import types
from collections.abc import Iterable, Iterator, Mapping
from typing import Annotated, Any, Union, get_args, get_origin, get_type_hints

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - optional dependency
    BaseModel = None


UnionType = getattr(types, "UnionType", None)


def is_list_validator(validator: Any) -> bool:
    """Check whether the validator describes an iterable of string keys.

    Args:
        validator: Validator supplied by the user.

    Returns:
        `True` when the validator is an iterable of strings, otherwise `False`.
    """
    return (
        not isinstance(validator, Mapping)
        and isinstance(validator, Iterable)
        and all(isinstance(item, str) for item in validator)
    )


def is_dict_validator(validator: Any) -> bool:
    """Check whether the validator describes a mapping of key→type pairs.

    Args:
        validator: Validator supplied by the user.

    Returns:
        `True` when the validator is a mapping that maps strings to types,
        otherwise `False`.
    """
    return isinstance(validator, Mapping) and all(
        isinstance(key, str) and isinstance(value, type)
        for key, value in validator.items()
    )


def is_dataclass_validator(validator: Any) -> bool:
    """Check whether the validator is a dataclass type.

    Args:
        validator: Validator supplied by the user.

    Returns:
        `True` when the validator is a dataclass, otherwise `False`.
    """
    return isinstance(validator, type) and dataclasses.is_dataclass(validator)


def is_pydantic_validator(validator: Any) -> bool:
    """Check whether the validator is a Pydantic BaseModel type.

    Args:
        validator: Validator supplied by the user.

    Returns:
        `True` when the validator is a Pydantic BaseModel type, otherwise `False`.
    """
    return (
        BaseModel is not None
        and isinstance(validator, type)
        and issubclass(validator, BaseModel)
    )


def is_supported_validator(validator: Any) -> bool:
    """Check whether the validator is of a supported type.

    Args:
        validator: Validator supplied by the user.

    Returns:
        `True` when the validator is of a supported type, otherwise `False`.
    """
    return any(
        (
            is_list_validator(validator),
            is_dict_validator(validator),
            is_dataclass_validator(validator),
            is_pydantic_validator(validator),
        )
    )


def iter_model_fields(model_type: type) -> Iterator[tuple[str, Any]]:
    """Yield field names and annotations for dataclasses and BaseModels.

    Args:
        model_type: Validator type inspected for fields.

    Yields:
        Tuples of field name and its annotation.

    Raises:
        TypeError: When the provided model type is not supported.
    """
    if is_dataclass_validator(model_type):
        hints = get_type_hints(model_type)
        for field in dataclasses.fields(model_type):
            yield field.name, hints.get(field.name, field.type)
        return
    if is_pydantic_validator(model_type):
        model_fields = getattr(model_type, "model_fields", None)
        if model_fields is not None:
            for name, info in model_fields.items():
                annotation = getattr(info, "annotation", None)
                if _is_pydantic_undefined(annotation):
                    annotation = None
                if annotation is None:
                    annotation = getattr(model_type, "__annotations__", {}).get(name)
                yield name, annotation
            return
        legacy_fields = getattr(model_type, "__fields__", {})
        for name, info in legacy_fields.items():
            annotation = getattr(info, "annotation", None)
            if _is_pydantic_undefined(annotation):
                annotation = None
            yield name, annotation

    message = f"unsupported model type: {model_type!r}"
    raise TypeError(message)


def resolve_model_type(hint: Any) -> type | None:
    """Resolve a validator type from the provided annotation hint.

    Args:
        hint: Annotation that may reference nested dataclasses or Pydantic
            models.

    Returns:
        The validator model type (one of dataclass or Pydantic model) referenced by
        `hint` or `None`.
    """
    if isinstance(hint, type):
        if is_dataclass_validator(hint) or is_pydantic_validator(hint):
            return hint
        return None
    origin = get_origin(hint)
    if origin is Annotated:
        args = get_args(hint)
        if not args:
            return None
        return resolve_model_type(args[0])
    if origin is Union or origin is UnionType:
        for arg in get_args(hint):
            if arg is type(None):
                continue
            nested = resolve_model_type(arg)
            if nested is not None:
                return nested
    return None


def _is_pydantic_undefined(annotation: Any) -> bool:
    """Return True when annotation represents Pydantic's undefined sentinel."""
    if annotation is None:
        return False
    name = getattr(annotation, "__name__", "") or annotation.__class__.__name__
    return "PydanticUndefined" in name


def collect_env_override_paths(validator: type | None) -> dict[tuple[str, ...], str]:
    """Collect override mappings for a model validator hierarchy.

    Only acts on dataclass or Pydantic model types, otherwise returns an empty dict.

    Args:
        validator: Validator type that may declare `__env_overrides__`.

    Returns:
        Mapping from dotted validator field paths to environment variable names.

    Raises:
        AttributeError: When the validator's `__env_overrides__` mapping
            contains invalid field names.
    """
    overrides: dict[tuple[str, ...], str] = {}
    if validator is None or not (
        is_dataclass_validator(validator) or is_pydantic_validator(validator)
    ):
        return overrides

    visited: set[type] = set()

    def _walk(current_type: type, prefix: tuple[str, ...]) -> None:
        if current_type in visited:
            return
        visited.add(current_type)
        mapping = getattr(current_type, "__env_overrides__", None)
        if isinstance(mapping, dict):
            for field_name, env_var in mapping.items():
                if field_name not in {
                    name for name, _ in iter_model_fields(current_type)
                }:
                    msg = f"invalid field name in __env_overrides__: {field_name!r}"
                    raise AttributeError(msg)
                overrides[(*prefix, field_name)] = env_var
        for field_name, annotation in iter_model_fields(current_type):
            nested = resolve_model_type(annotation)
            if nested is None:
                continue
            _walk(nested, (*prefix, field_name))

    _walk(validator, ())
    return overrides
