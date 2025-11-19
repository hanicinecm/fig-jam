"""Validation stage implementations for fig_jam."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from fig_jam.pipeline._model import ConfigBatch, ConfigSource, PipelineStage
from fig_jam.pipeline._validators import (
    is_dataclass_validator,
    is_dict_validator,
    is_list_validator,
    is_pydantic_validator,
)
from fig_jam.pipeline.override_sources import OverridesStatus


class ValidationStatus(str, Enum):
    """Status codes emitted by the validation stage."""

    SUCCESS = "success"
    VALIDATION_ERROR = "validation-error"


def _record_mapping_error(source: ConfigSource) -> None:
    source.stage_status = ValidationStatus.VALIDATION_ERROR
    source.stage_error_metadata = {"message": "payload must be a mapping"}


def _handle_list_validator(
    source: ConfigSource, payload: Any, validator: list[str]
) -> bool:
    if not isinstance(payload, Mapping):
        _record_mapping_error(source)
        return True
    filtered = {key: payload[key] for key in validator if key in payload}
    source.payload = filtered
    source.stage_status = ValidationStatus.SUCCESS
    source.stage_error_metadata = {}
    return True


def _handle_dict_validator(
    source: ConfigSource, payload: Any, validator: dict[str, type]
) -> bool:
    if not isinstance(payload, Mapping):
        _record_mapping_error(source)
        return True
    validated: dict[str, object] = {}
    for key, expected_type in validator.items():
        if key not in payload:
            source.stage_status = ValidationStatus.VALIDATION_ERROR
            source.stage_error_metadata = {"missing_key": key}
            return True
        try:
            validated[key] = expected_type(payload[key])
        except (TypeError, ValueError) as error:
            source.stage_status = ValidationStatus.VALIDATION_ERROR
            source.stage_error_metadata = {"key": key, "exception": error}
            return True
    source.payload = validated
    source.stage_status = ValidationStatus.SUCCESS
    source.stage_error_metadata = {}
    return True


def _handle_model_validator(
    source: ConfigSource, payload: Any, model_validator: type[Any]
) -> bool:
    if not isinstance(payload, Mapping):
        _record_mapping_error(source)
        return True
    try:
        instance = model_validator(**payload)
    except (TypeError, ValueError) as error:
        source.stage_status = ValidationStatus.VALIDATION_ERROR
        source.stage_error_metadata = {
            "message": str(error),
            "exception": error,
        }
        return True
    source.payload = instance
    source.stage_status = ValidationStatus.SUCCESS
    source.stage_error_metadata = {}
    return True


def validate(batch: ConfigBatch) -> ConfigBatch:
    """Apply the provided validator to every active source."""
    if batch.error_code is not None:
        return batch
    validator = batch.validator
    for source in batch.sources:
        if source.stage_status is not OverridesStatus.SUCCESS:
            continue
        source.last_visited_stage = PipelineStage.VALIDATE
        payload = source.payload
        if validator is None:
            source.stage_status = ValidationStatus.SUCCESS
            source.stage_error_metadata = {}
            continue
        if is_list_validator(validator) and _handle_list_validator(
            source, payload, validator
        ):
            continue
        if is_dict_validator(validator) and _handle_dict_validator(
            source, payload, validator
        ):
            continue
        if (
            is_dataclass_validator(validator) or is_pydantic_validator(validator)
        ) and _handle_model_validator(source, payload, validator):
            continue
        source.stage_status = ValidationStatus.VALIDATION_ERROR
        source.stage_error_metadata = {"message": "unsupported validator type"}
    return batch
