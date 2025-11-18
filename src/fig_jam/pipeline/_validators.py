"""Helpers for validator inspection."""

from __future__ import annotations

import dataclasses
import types
from collections.abc import Iterator
from typing import Annotated, Any, Union, get_args, get_origin

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - optional dependency
    BaseModel = None


UnionType = getattr(types, "UnionType", None)


def is_list_validator(validator: Any) -> bool:
    """Check whether the validator describes a list of string keys.

    Args:
        validator: Validator supplied by the user.

    Returns:
        `True` when the validator is a list of strings, otherwise `False`.
    """
    return isinstance(validator, list) and all(
        isinstance(item, str) for item in validator
    )


def is_dict_validator(validator: Any) -> bool:
    """Check whether the validator describes a dict of key→type pairs.

    Args:
        validator: Validator supplied by the user.

    Returns:
        `True` when the validator is a dict that maps strings to types,
        otherwise `False`.
    """
    return isinstance(validator, dict) and all(
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
        for field in dataclasses.fields(model_type):
            yield field.name, field.type
        return
    if is_pydantic_validator(model_type):
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
