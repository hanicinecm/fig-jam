"""Override stage implementations for fig_jam."""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from enum import Enum

from fig_jam.pipeline._model import ConfigBatch, PipelineStage
from fig_jam.pipeline._pipeline_utils import (
    apply_nested_override,
    collect_env_override_paths,
    get_model_validator_type,
)
from fig_jam.pipeline.parse_sources import ParsingStatus


class OverridesStatus(str, Enum):
    """Status codes emitted by the override stage."""

    CONFIGURED = "configured"
    NOT_CONFIGURED = "not-configured"
    FIELD_ERROR = "field-error"


def override(batch: ConfigBatch) -> ConfigBatch:
    """Apply environment overrides defined by dataclass or Pydantic validators."""
    validator_type = get_model_validator_type(batch.validator)
    overrides = collect_env_override_paths(validator_type)
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
            if not apply_nested_override(payload, path, env_value):
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
