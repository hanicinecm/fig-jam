"""Validation stage implementations for fig_jam."""

from __future__ import annotations

import dataclasses
import typing
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
    MISSING_KEYS_ERROR = "missing-keys-error"
    TYPE_COERCION_ERROR = "type-coercion-error"
    DATACLASS_INSTANTIATION_ERROR = "dataclass-instantiation-error"
    PYDANTIC_VALIDATION_ERROR = "pydantic-validation-error"


def _handle_list_validator(
    source: ConfigSource,
    payload: Mapping[str, Any],
    validator: list[str],
    *,
    strict: bool,
) -> None:
    missing_keys = [key for key in validator if key not in payload]
    if missing_keys:
        source.stage_status = ValidationStatus.MISSING_KEYS_ERROR
        source.stage_error_metadata = {"missing_keys": missing_keys}
        return
    if strict:
        source.payload = {key: payload[key] for key in validator}
    else:
        source.payload = dict(payload)
    source.stage_status = ValidationStatus.SUCCESS
    source.stage_error_metadata = {}


def _coerce_value(value: Any, expected_type: type) -> tuple[Any, Exception | None]:
    """Attempt to coerce a value to the expected type.

    Args:
        value: The value to coerce.
        expected_type: The type to coerce to.

    Returns:
        A tuple of (coerced_value, error). If successful, error is None.
        If coercion fails, coerced_value is None and error contains the exception.
    """
    try:
        if expected_type is bool:
            return _coerce_to_bool(value), None
        return expected_type(value), None
    except (TypeError, ValueError) as error:
        return None, error


def _coerce_to_bool(value: Any) -> bool:
    """Coerce a value to bool with special handling for string representations.

    Recognizes common falsy string values ("false", "False", "FALSE", "0") as
    False. All other non-empty strings are True. Non-string values use standard
    bool() coercion.

    Args:
        value: The value to coerce to bool.

    Returns:
        The boolean interpretation of the value.
    """
    if isinstance(value, str):
        if not value:
            return False
        falsy_strings = {"false", "False", "FALSE", "0"}
        return value not in falsy_strings
    return bool(value)


def _handle_dict_validator(
    source: ConfigSource,
    payload: Mapping[str, Any],
    validator: dict[str, type],
) -> None:
    missing_keys = [key for key in validator if key not in payload]
    if missing_keys:
        source.stage_status = ValidationStatus.MISSING_KEYS_ERROR
        source.stage_error_metadata = {"missing_keys": missing_keys}
        return
    validated: dict[str, object] = {}
    coercion_errors: dict[str, Exception] = {}
    for key, expected_type in validator.items():
        coerced, error = _coerce_value(payload[key], expected_type)
        if error is not None:
            coercion_errors[key] = error
        else:
            validated[key] = coerced
    if coercion_errors:
        source.stage_status = ValidationStatus.TYPE_COERCION_ERROR
        source.stage_error_metadata = {"coercion_errors": coercion_errors}
        return
    source.payload = validated
    source.stage_status = ValidationStatus.SUCCESS
    source.stage_error_metadata = {}


def _handle_dataclass_validator(
    source: ConfigSource,
    payload: Mapping[str, Any],
    dataclass_type: type[Any],
) -> None:
    """Handle dataclass validator by coercing values and instantiating.

    Coerces all provided fields to their declared types, then attempts to
    instantiate the dataclass. Missing required fields are reported by the
    dataclass constructor via TypeError.
    """
    # TODO: Coerce nested dataclass/Pydantic fields recursively and aggregate
    # missing-field errors instead of deferring to constructor errors.
    coerced: dict[str, object] = {}
    coercion_errors: dict[str, Exception] = {}
    resolved_hints = typing.get_type_hints(dataclass_type)
    for field in dataclasses.fields(dataclass_type):
        if field.name not in payload:
            continue  # Let dataclass handle missing (uses default or raises)
        expected_type = resolved_hints.get(field.name, field.type)
        nested_value = payload[field.name]
        if is_dataclass_validator(expected_type):
            if not isinstance(nested_value, Mapping):
                coercion_errors[field.name] = TypeError(
                    f"expected mapping for nested dataclass '{field.name}'"
                )
                continue
            try:
                coerced[field.name] = expected_type(**nested_value)
            except Exception as error:  # noqa: BLE001
                coercion_errors[field.name] = error
            continue
        if is_pydantic_validator(expected_type):
            if not isinstance(nested_value, Mapping):
                coercion_errors[field.name] = TypeError(
                    f"expected mapping for nested model '{field.name}'"
                )
                continue
            try:
                coerced[field.name] = expected_type(**nested_value)
            except (TypeError, ValueError) as error:
                coercion_errors[field.name] = error
            continue
        value, error = _coerce_value(nested_value, expected_type)  # type: ignore[arg-type]
        if error is not None:
            coercion_errors[field.name] = error
        else:
            coerced[field.name] = value
    if coercion_errors:
        source.stage_status = ValidationStatus.TYPE_COERCION_ERROR
        source.stage_error_metadata = {"coercion_errors": coercion_errors}
        return
    try:
        instance = dataclass_type(**coerced)
    except TypeError as error:
        source.stage_status = ValidationStatus.DATACLASS_INSTANTIATION_ERROR
        source.stage_error_metadata = {
            "message": str(error),
            "exception": error,
        }
        return
    source.payload = instance
    source.stage_status = ValidationStatus.SUCCESS
    source.stage_error_metadata = {}


def _handle_pydantic_validator(
    source: ConfigSource,
    payload: Mapping[str, Any],
    model_type: type[Any],
) -> None:
    try:
        instance = model_type(**payload)
    except (TypeError, ValueError) as error:
        source.stage_status = ValidationStatus.PYDANTIC_VALIDATION_ERROR
        source.stage_error_metadata = {
            "message": str(error),
            "exception": error,
        }
        return
    source.payload = instance
    source.stage_status = ValidationStatus.SUCCESS
    source.stage_error_metadata = {}


def validate(batch: ConfigBatch) -> ConfigBatch:
    """Apply the provided validator to every active source."""
    if batch.error_code is not None:
        return batch
    validator = batch.validator
    for source in batch.sources:
        if source.stage_status is not OverridesStatus.SUCCESS:
            continue
        source.last_visited_stage = PipelineStage.VALIDATE
        payload: Mapping[str, Any] = source.payload  # type: ignore[assignment]
        if validator is None:
            source.stage_status = ValidationStatus.SUCCESS
            source.stage_error_metadata = {}
            continue
        if is_list_validator(validator):
            _handle_list_validator(source, payload, validator, strict=batch.strict)
            continue
        if is_dict_validator(validator):
            _handle_dict_validator(source, payload, validator)
            continue
        if is_dataclass_validator(validator):
            _handle_dataclass_validator(source, payload, validator)
            continue
        if is_pydantic_validator(validator):
            _handle_pydantic_validator(source, payload, validator)
            continue
        msg = f"unsupported validator type: {type(validator)}"
        raise TypeError(msg)
    return batch
