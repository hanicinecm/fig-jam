"""Override stage implementations for fig_jam."""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from enum import Enum
from typing import Any

from fig_jam.pipeline._model import ConfigBatch, PipelineStage
from fig_jam.pipeline.parse_sources import ParsingStatus


class OverridesStatus(str, Enum):
    """Status codes emitted by the override stage."""

    SUCCESS = "success"


def _apply_nested_override(
    payload: MutableMapping[str, Any], path: tuple[str, ...], value: str
) -> None:
    """Insert a value into the payload using the dotted path index.

    Designed to work on an empty payload also, creating nested mappings and the final
    key, if they do not exist.

    Args:
        payload: Mutable mapping representing the current validator payload.
        path: Sequence of keys describing the nested location to override.
        value: Environment-provided value applied to the final key.
    """
    node: MutableMapping[str, Any] = payload
    for segment in path[:-1]:
        next_node = node.get(segment)
        if next_node is None:
            next_node = {}
            node[segment] = next_node
        elif not isinstance(next_node, MutableMapping):
            msg = (
                f"Expected mapping at path segment '{segment}', but found "
                f"{type(next_node).__name__}"
            )
            raise TypeError(msg)
        node = next_node

    final_key = path[-1]
    node[final_key] = value


def override(batch: ConfigBatch) -> ConfigBatch:
    """Apply environment overrides defined by dataclass or Pydantic validators."""
    if batch.error_code is not None:
        return batch

    overrides = batch.env_overrides

    for source in batch.sources:
        if source.stage_status is not ParsingStatus.SUCCESS:
            continue

        source.last_visited_stage = PipelineStage.OVERRIDE

        payload = source.payload
        if not isinstance(payload, MutableMapping):
            # just for clarity and type checker, at this stage, payload will be a dict
            msg = "Expected mutable mapping payload for overrides"
            raise TypeError(msg)

        # Apply the overrides to the payload, if they exist in the environment
        applied: dict[str, str] = {}
        for path, env_var in overrides.items():
            env_value = os.environ.get(env_var)
            if env_value is None:
                continue
            _apply_nested_override(payload, path, env_value)
            applied[".".join(path)] = env_var

        source.applied_overrides.update(applied)
        source.stage_status = OverridesStatus.SUCCESS

    return batch
