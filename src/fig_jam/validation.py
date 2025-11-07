"""Validate configuration candidates produced by discovery and overrides.

This module dispatches across supported validator styles (lists, dictionaries,
dataclasses, and Pydantic models) and converts results into structured
diagnostics. It is consumed exclusively by `fig_jam.loader`, and couples to
`fig_jam.discovery` for discovery outputs and `fig_jam.exceptions` for
diagnostic records.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import MISSING, fields, is_dataclass
from typing import Any, get_type_hints

from fig_jam.exceptions import DiagnosticDetail
from fig_jam.pipeline import PipelineBatch, PipelineCandidate
from fig_jam.utils.mappings import freeze_mapping
from fig_jam.utils.types import coerce_for_annotation, coerce_value, describe_annotation
from fig_jam.utils.validators import (
    is_dataclass_validator,
    is_pydantic_validator,
    is_string_sequence_validator,
)

try:
    from pydantic import BaseModel as _PydanticBaseModel  # type: ignore[import]
    from pydantic import (  # type: ignore[import]
        ValidationError as _PydanticValidationError,
    )
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    _PydanticBaseModel = None  # type: ignore[assignment]
    _PydanticValidationError = None  # type: ignore[assignment]


def validate_candidates(
    batch: PipelineBatch,
    validator: Any,
) -> PipelineBatch:
    """Run the validation stage over the provided pipeline batch.

    Args:
        batch: Pipeline candidates produced by discovery.
        validator: Validator descriptor supplied to `get_config`.

    Returns:
        Updated pipeline batch reflecting validation outcomes.
    """

    def _validate(candidate: PipelineCandidate) -> PipelineCandidate:
        if candidate.data is None:
            return candidate
        if not isinstance(candidate.data, Mapping):
            detail = DiagnosticDetail(
                stage="validation.input",
                message="Candidate payload is not a mapping and cannot be validated.",
                data={"path": str(candidate.source_path)},
            )
            return candidate.append_diagnostics(detail).with_data(None)

        try:
            validated, new_diagnostics = _run_validation(
                candidate.data,
                validator,
            )
        except _ValidationFailureError as exc:
            updated = candidate.extend_diagnostics(exc.diagnostics)
            updated = updated.append_diagnostics(exc.diagnostic)
            return updated.with_data(None)

        updated = candidate.extend_diagnostics(new_diagnostics)
        return updated.with_data(validated)

    return batch.map(_validate)


class _ValidationFailureError(Exception):
    """Raised when validation fails for a candidate."""

    def __init__(
        self,
        diagnostic: DiagnosticDetail,
        *,
        diagnostics: Sequence[DiagnosticDetail] | None = None,
    ) -> None:
        """Store the diagnostic detail associated with the failure."""
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic
        self.diagnostics = tuple(diagnostics or ())


def _run_validation(
    data: Mapping[str, Any],
    validator: Any,
) -> tuple[Any, tuple[DiagnosticDetail, ...]]:
    """Run the validator against the provided mapping.

    Args:
        data: Mapping produced by the discovery stage.
        validator: Validator descriptor provided by the caller.

    Returns:
        Pair containing the validated payload and additional diagnostics.

    Raises:
        TypeError: If the validator type is unsupported.
    """
    if validator is None:
        detail = DiagnosticDetail(
            stage="validation.none",
            message="No validator supplied; using discovered mapping.",
        )
        return data, (detail,)

    if is_string_sequence_validator(validator):
        return _validate_key_list(data, validator)

    if isinstance(validator, Mapping):
        return _validate_typed_mapping(data, validator)

    if is_dataclass_validator(validator):
        return _validate_dataclass(data, validator)

    if is_pydantic_validator(validator):
        return _validate_pydantic(data, validator)

    message = "Unsupported validator type."
    raise TypeError(message)


def _validate_key_list(
    data: Mapping[str, Any], validator: Sequence[str]
) -> tuple[Mapping[str, Any], tuple[DiagnosticDetail, ...]]:
    """Validate configuration using a list of keys.

    Args:
        data: Mapping produced by discovery.
        validator: Sequence of keys that must be present.

    Returns:
        Pair containing the filtered mapping and validation diagnostics.

    Raises:
        _ValidationFailureError: If required keys are missing.
    """
    missing = [key for key in validator if key not in data]
    if missing:
        detail = DiagnosticDetail(
            stage="validation.list",
            message="Required keys are missing from configuration data.",
            data={"missing_keys": tuple(missing)},
        )
        raise _ValidationFailureError(detail)

    filtered = freeze_mapping({key: data[key] for key in validator})
    detail = DiagnosticDetail(
        stage="validation.list",
        message="Filtered configuration data using list validator.",
        data={"keys": tuple(validator)},
    )
    return filtered, (detail,)


def _validate_typed_mapping(
    data: Mapping[str, Any], validator: Mapping[str, Any]
) -> tuple[Mapping[str, Any], tuple[DiagnosticDetail, ...]]:
    """Validate configuration with a mapping of keys to types.

    Args:
        data: Mapping produced by discovery.
        validator: Mapping describing required keys and expected types.

    Returns:
        Pair containing the coerced mapping and validation diagnostics.

    Raises:
        TypeError: If the validator mapping contains unsupported entries.
        _ValidationFailureError: If keys are missing or coercion fails.
    """
    for key, target in validator.items():
        if not isinstance(key, str):
            message = "Validator mapping keys must be strings."
            raise TypeError(message)
        if not isinstance(target, type):
            message = "Validator mapping values must be types."
            raise TypeError(message)

    missing = [key for key in validator if key not in data]
    if missing:
        detail = DiagnosticDetail(
            stage="validation.dict",
            message="Required keys are missing from configuration data.",
            data={"missing_keys": tuple(missing)},
        )
        raise _ValidationFailureError(detail)

    coerced: dict[str, Any] = {}
    failures: list[str] = []
    for key, target_type in validator.items():
        value = data[key]
        try:
            coerced[key] = coerce_value(value, target_type)
        except (TypeError, ValueError) as exc:
            failure_message = (
                f"{key}: expected {target_type.__name__}, "
                f"received {type(value).__name__} ({exc})"
            )
            failures.append(failure_message)

    if failures:
        detail = DiagnosticDetail(
            stage="validation.dict",
            message="Failed to coerce configuration values to required types.",
            data={"errors": tuple(failures)},
        )
        raise _ValidationFailureError(detail)

    detail = DiagnosticDetail(
        stage="validation.dict",
        message="Validated configuration using key/type mapping.",
        data={"keys": tuple(coerced)},
    )
    return freeze_mapping(coerced), (detail,)


def _is_dataclass_validator(validator: Any) -> bool:
    """Determine whether the validator is a dataclass type.

    Args:
        validator: Validator descriptor under inspection.

    Returns:
        Boolean indicating whether the validator is a dataclass.
    """
    return isinstance(validator, type) and is_dataclass(validator)


def _validate_dataclass(
    data: Mapping[str, Any],
    validator: type,
) -> tuple[Any, tuple[DiagnosticDetail, ...]]:
    """Validate configuration using a dataclass validator.

    Args:
        data: Mapping produced by discovery.
        validator: Dataclass type describing expected configuration fields.

    Returns:
        Pair containing the dataclass instance and associated diagnostics.

    Raises:
        _ValidationFailureError: If required fields are missing or coercion
        fails.
    """
    field_definitions = tuple(fields(validator))
    payload: dict[str, Any] = {}
    errors: list[str] = []
    type_hints = get_type_hints(validator)

    for field in field_definitions:
        name = field.name
        has_default = (
            field.default is not MISSING
            or getattr(field, "default_factory", MISSING) is not MISSING
        )

        if name not in data:
            if has_default:
                continue
            errors.append(f"{name}: missing required field")
            continue

        value = data[name]
        annotation = type_hints.get(name, field.type)
        try:
            payload[name] = coerce_for_annotation(value, annotation)
        except (TypeError, ValueError) as exc:
            error_message = (
                f"{name}: expected {describe_annotation(annotation)}, "
                f"received {type(value).__name__} ({exc})"
            )
            errors.append(error_message)

    if errors:
        detail = DiagnosticDetail(
            stage="validation.dataclass",
            message="Dataclass validation failed.",
            data={"errors": tuple(errors)},
        )
        raise _ValidationFailureError(detail)

    try:
        instance = validator(**payload)
    except TypeError as exc:
        detail = DiagnosticDetail(
            stage="validation.dataclass",
            message="Dataclass instantiation failed.",
            data={"error": str(exc)},
        )
        raise _ValidationFailureError(detail) from exc

    detail = DiagnosticDetail(
        stage="validation.dataclass",
        message="Validated configuration using dataclass schema.",
        data={"fields": tuple(payload)},
    )
    return instance, (detail,)


def _validate_pydantic(
    data: Mapping[str, Any],
    validator: type,
) -> tuple[Any, tuple[DiagnosticDetail, ...]]:
    """Validate configuration using a Pydantic model.

    Args:
        data: Mapping produced by discovery.
        validator: Pydantic model type supplied by the caller.

    Returns:
        Pair containing the Pydantic model instance and diagnostics.

    Raises:
        RuntimeError: If Pydantic is unavailable at runtime.
        _ValidationFailureError: When validation fails inside Pydantic.
    """
    if (
        _PydanticBaseModel is None or _PydanticValidationError is None
    ):  # pragma: no cover - optional dependency guard
        message = "Pydantic validator requested but pydantic is not available."
        raise RuntimeError(message)

    try:
        instance = validator(**dict(data))
    except _PydanticValidationError as exc:  # type: ignore[misc]
        detail = DiagnosticDetail(
            stage="validation.pydantic",
            message="Pydantic validation failed.",
            data={"errors": exc.errors() if hasattr(exc, "errors") else str(exc)},
        )
        raise _ValidationFailureError(detail) from exc

    detail = DiagnosticDetail(
        stage="validation.pydantic",
        message="Validated configuration using Pydantic model.",
        data={"model": f"{validator.__module__}.{validator.__qualname__}"},
    )
    return instance, (detail,)
