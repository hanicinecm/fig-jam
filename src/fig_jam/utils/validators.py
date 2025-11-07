"""Helpers for working with validator descriptors across the pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import fields, is_dataclass
from typing import Any

try:
    from pydantic import BaseModel as _PydanticBaseModel  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    _PydanticBaseModel = None  # type: ignore[assignment]

_SEQUENCE_EXCLUSIONS = (str, bytes, bytearray)


def is_string_sequence_validator(validator: Any) -> bool:
    """Return whether the validator is a sequence of strings."""
    if isinstance(validator, _SEQUENCE_EXCLUSIONS):
        return False
    if isinstance(validator, Sequence):
        return all(isinstance(item, str) for item in validator)
    return False


def is_dataclass_validator(validator: Any) -> bool:
    """Return whether the validator represents a dataclass type."""
    return isinstance(validator, type) and is_dataclass(validator)


def get_dataclass_field_names(validator: type[Any]) -> list[str]:
    """Return the declared field names for a dataclass validator."""
    return [field.name for field in fields(validator)]


def is_pydantic_validator(validator: Any) -> bool:
    """Return whether the validator represents a Pydantic model."""
    if _PydanticBaseModel is None or not isinstance(validator, type):
        return False
    return issubclass(validator, _PydanticBaseModel)


def get_pydantic_field_names(validator: type[Any]) -> list[str]:
    """Return the declared field names for a Pydantic model."""
    if hasattr(validator, "model_fields"):
        fields_attr = validator.model_fields
        if isinstance(fields_attr, dict):
            return list(fields_attr)
        return list(fields_attr.keys())  # pragma: no cover - defensive branch

    if hasattr(validator, "__fields__"):
        fields_attr = validator.__fields__
        if isinstance(fields_attr, dict):
            return list(fields_attr)
        return list(fields_attr.keys())  # pragma: no cover - defensive branch

    return []
