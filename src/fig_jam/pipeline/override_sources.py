"""Override stage implementations for fig_jam."""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from enum import Enum
from typing import Any

from fig_jam.pipeline._model import ConfigBatch, PipelineStage
from fig_jam.pipeline._validators import (
    is_dataclass_validator,
    is_pydantic_validator,
    iter_model_fields,
    resolve_model_type,
)
from fig_jam.pipeline.parse_sources import ParsingStatus


class OverridesStatus(str, Enum):
    """Status codes emitted by the override stage."""

    CONFIGURED = "configured"
    NOT_CONFIGURED = "not-configured"
    FIELD_ERROR = "field-error"


def _collect_env_override_paths(validator: type | None) -> dict[tuple[str, ...], str]:
    """Collect override mappings for a model validator hierarchy.

    Only acts on dataclass or Pydantic model types, otherwise returns an empty dict.

    Args:
        validator: Validator type that may declare `__env_overrides__`.

    Returns:
        Mapping from dotted validator field paths to environment variable names.
    """
    overrides: dict[tuple[str, ...], str] = {}
    if (
        validator is None
        or not (
            is_dataclass_validator(validator) or is_pydantic_validator(validator)
        )
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
                overrides[(*prefix, field_name)] = env_var
        for field_name, annotation in iter_model_fields(current_type):
            nested = resolve_model_type(annotation)
            if nested is None:
                continue
            _walk(nested, (*prefix, field_name))

    _walk(validator, ())
    return overrides


def _apply_nested_override(
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


def override(batch: ConfigBatch) -> ConfigBatch:
    """Apply environment overrides defined by dataclass or Pydantic validators."""
    if batch.error_code is not None:
        return batch
    overrides = _collect_env_override_paths(batch.validator)
    for source in batch.sources:
        if source.stage_status is not ParsingStatus.PARSED:
            continue
        source.last_visited_stage = PipelineStage.OVERRIDE
        if not overrides:
            source.stage_status = OverridesStatus.NOT_CONFIGURED
            source.stage_error_metadata = {}
            continue
        payload = source.payload
        if not isinstance(payload, MutableMapping):
            source.stage_status = OverridesStatus.FIELD_ERROR
            source.stage_error_metadata = {"path": "", "validator_field": ""}
            continue
        applied: dict[str, str] = {}
        for path, env_var in overrides.items():
            env_value = os.environ.get(env_var)
            if env_value is None:
                continue
            if not _apply_nested_override(payload, path, env_value):
                source.stage_status = OverridesStatus.FIELD_ERROR
                source.stage_error_metadata = {
                    "path": ".".join(path),
                    "validator_field": path[-1],
                }
                break
            applied[".".join(path)] = env_var
        else:
            source.applied_overrides.update(applied)
            source.stage_status = OverridesStatus.CONFIGURED
            source.stage_error_metadata = {}
            continue
    return batch
