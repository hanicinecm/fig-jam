"""Resolve validator-defined environment overrides.

This module is consumed by `fig_jam.validation` to translate optional
`__env_overrides__` mappings declared on dataclass and Pydantic validators
into runtime configuration updates.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fig_jam.exceptions import DiagnosticDetail


def resolve_validator_overrides(
    validator: type[Any],
    *,
    field_names: Sequence[str],
    environment: Mapping[str, str],
) -> tuple[dict[str, str], tuple[DiagnosticDetail, ...]]:
    """Resolve validator-defined environment overrides.

    Args:
        validator: Dataclass or Pydantic validator declaring overrides.
        field_names: Iterable of valid field names for the validator.
        environment: Mapping of environment variables to inspect.

    Returns:
        Pair containing the overrides that should be applied (field → value)
        and diagnostics describing any updates that occurred.

    Raises:
        TypeError: If the override mapping is not well-formed.
    """
    overrides = getattr(validator, "__env_overrides__", None)
    if overrides is None:
        return {}, ()

    if not isinstance(overrides, Mapping):
        message = (
            f"{_describe_validator(validator)}.__env_overrides__ must be a mapping "
            "of field names to environment variable names."
        )
        raise TypeError(message)

    valid_fields = set(field_names)
    applied: dict[str, str] = {}
    diagnostics: list[DiagnosticDetail] = []

    for field_name, env_name in overrides.items():
        if not isinstance(field_name, str):
            message = (
                f"{_describe_validator(validator)}.__env_overrides__ keys must be "
                "strings referencing validator fields."
            )
            raise TypeError(message)

        if field_name not in valid_fields:
            message = (
                f"{_describe_validator(validator)}.__env_overrides__ references "
                f"unknown field '{field_name}'."
            )
            raise TypeError(message)

        if not isinstance(env_name, str):
            message = (
                f"{_describe_validator(validator)}.__env_overrides__ values must be "
                "strings naming environment variables."
            )
            raise TypeError(message)

        if env_name in environment:
            value = environment[env_name]
            applied[field_name] = value
            diagnostics.append(
                DiagnosticDetail(
                    stage="validation.overrides",
                    message="Applied validator-defined environment override.",
                    data={"field": field_name, "environment_variable": env_name},
                )
            )

    return applied, tuple(diagnostics)


def _describe_validator(validator: type[Any]) -> str:
    """Return a user-friendly identifier for a validator type."""
    return f"{validator.__module__}.{validator.__qualname__}"
