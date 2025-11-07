"""Shared utility helpers used across fig_jam modules.

This package groups reusable functionality that is not logically scoped to a
single pipeline stage. Utilities are organised into focused modules to avoid
circular dependencies and keep imports explicit.
"""

from fig_jam.utils.mappings import ensure_mapping, freeze_mapping
from fig_jam.utils.paths import canonicalize_path
from fig_jam.utils.types import (
    coerce_bool_value,
    coerce_for_annotation,
    coerce_value,
    describe_annotation,
)
from fig_jam.utils.validators import (
    get_dataclass_field_names,
    get_pydantic_field_names,
    is_dataclass_validator,
    is_pydantic_validator,
    is_string_sequence_validator,
)

__all__ = [
    "canonicalize_path",
    "coerce_bool_value",
    "coerce_for_annotation",
    "coerce_value",
    "describe_annotation",
    "ensure_mapping",
    "freeze_mapping",
    "get_dataclass_field_names",
    "get_pydantic_field_names",
    "is_dataclass_validator",
    "is_pydantic_validator",
    "is_string_sequence_validator",
]
