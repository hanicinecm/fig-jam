"""Validate configuration candidates produced by discovery and overrides.

This module dispatches across supported validator styles (lists, dictionaries,
dataclasses, and Pydantic models) and converts results into structured
diagnostics. It is consumed exclusively by `fig_jam.loader`, and couples to
`fig_jam.discovery` for discovery outputs and `fig_jam.exceptions` for
diagnostic records.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import MISSING, dataclass, fields, is_dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Union, get_args, get_origin, get_type_hints

from fig_jam.discovery import DiscoveryResult
from fig_jam.exceptions import DiagnosticDetail
from fig_jam.overrides import resolve_validator_overrides

try:
    from pydantic import BaseModel as _PydanticBaseModel  # type: ignore[import]
    from pydantic import (  # type: ignore[import]
        ValidationError as _PydanticValidationError,
    )
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    _PydanticBaseModel = None  # type: ignore[assignment]
    _PydanticValidationError = None  # type: ignore[assignment]

_SEQUENCE_EXCLUSIONS = (str, bytes, bytearray)


@dataclass(frozen=True)
class ValidationCandidate:
    """Represent a candidate configuration after validation.

    Attributes:
        source_path: Original source path for the candidate.
        data: Validated configuration payload when available.
        diagnostics: Diagnostics collected during discovery and validation.
    """

    source_path: str
    data: Any | None
    diagnostics: Sequence[DiagnosticDetail]

    def __post_init__(self) -> None:
        """Freeze diagnostics and mapping data for consistency."""
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if isinstance(self.data, Mapping) and not isinstance(
            self.data, MappingProxyType
        ):
            # Preserve mapping immutability expectations downstream.
            object.__setattr__(self, "data", MappingProxyType(dict(self.data)))


@dataclass(frozen=True)
class ValidationResult:
    """Aggregate validation outcome for downstream consumption by the loader.

    Attributes:
        candidates: Ordered collection of validation candidates.
    """

    candidates: Sequence[ValidationCandidate]

    def __post_init__(self) -> None:
        """Freeze the candidate sequence to guarantee deterministic ordering."""
        object.__setattr__(self, "candidates", tuple(self.candidates))


def validate_candidates(
    discovery_result: DiscoveryResult,
    validator: Any,
    *,
    environment: Mapping[str, str] | None = None,
) -> ValidationResult:
    """Validate discovery results using the supplied validator.

    Args:
        discovery_result: Output from the discovery stage containing parsed
            candidates and diagnostics.
        validator: Validator descriptor supplied to `get_config`.
        environment: Optional mapping of environment variables used to resolve
            validator-defined overrides. Defaults to ``os.environ`` when
            omitted.

    Returns:
        Validation results containing updated candidates with validation
        diagnostics.
    """
    env_mapping = environment if environment is not None else os.environ
    candidates: list[ValidationCandidate] = []
    for candidate in discovery_result.candidates:
        diagnostics = list(candidate.diagnostics)
        if candidate.data is None:
            candidates.append(
                ValidationCandidate(
                    source_path=str(candidate.path),
                    data=None,
                    diagnostics=diagnostics,
                )
            )
            continue

        try:
            validated, new_diagnostics = _run_validation(
                candidate.data,
                validator,
                env_mapping,
            )
        except _ValidationFailureError as exc:
            diagnostics.extend(exc.diagnostics)
            diagnostics.append(exc.diagnostic)
            candidates.append(
                ValidationCandidate(
                    source_path=str(candidate.path),
                    data=None,
                    diagnostics=diagnostics,
                )
            )
        else:
            diagnostics.extend(new_diagnostics)
            candidates.append(
                ValidationCandidate(
                    source_path=str(candidate.path),
                    data=validated,
                    diagnostics=diagnostics,
                )
            )

    return ValidationResult(candidates=candidates)


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
    environment: Mapping[str, str],
) -> tuple[Any, tuple[DiagnosticDetail, ...]]:
    """Run the validator against the provided mapping.

    Args:
        data: Mapping produced by the discovery stage.
        validator: Validator descriptor provided by the caller.
        environment: Mapping of environment variables available for overrides.

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

    if _is_string_sequence_validator(validator):
        return _validate_key_list(data, validator)

    if isinstance(validator, Mapping):
        return _validate_typed_mapping(data, validator)

    if _is_dataclass_validator(validator):
        return _validate_dataclass(data, validator, environment)

    if _is_pydantic_validator(validator):
        return _validate_pydantic(data, validator, environment)

    message = "Unsupported validator type."
    raise TypeError(message)


def _is_string_sequence_validator(validator: Any) -> bool:
    """Determine whether the validator is a sequence of strings.

    Args:
        validator: Validator descriptor under inspection.

    Returns:
        Boolean indicating whether the validator is a string sequence.
    """
    if isinstance(validator, _SEQUENCE_EXCLUSIONS):
        return False
    if isinstance(validator, Sequence):
        return all(isinstance(item, str) for item in validator)
    return False


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

    filtered = MappingProxyType({key: data[key] for key in validator})
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
            coerced[key] = _coerce_value(value, target_type)
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
    return MappingProxyType(coerced), (detail,)


def _coerce_value(value: Any, target_type: type) -> Any:
    """Coerce a value to the target type with helpful error messaging.

    Args:
        value: Value to coerce.
        target_type: Target type expected by the validator.

    Returns:
        Value converted to the requested type.

    Raises:
        TypeError: If boolean or path coercion fails.
        ValueError: If built-in conversion raises `ValueError`.
    """
    if isinstance(value, target_type):
        return value

    if target_type is bool:
        return _coerce_bool_value(value)

    if target_type is Path:
        if isinstance(value, (str, Path)):
            return target_type(value)
        message = "Cannot coerce value to Path."
        raise TypeError(message)

    if target_type in {int, float, str}:
        return target_type(value)

    return target_type(value)


def _coerce_bool_value(value: Any) -> bool:
    """Coerce a value into a boolean using human-friendly rules.

    Args:
        value: Value to translate into a boolean.

    Returns:
        Boolean representation of the supplied value.

    Raises:
        TypeError: If the value cannot be interpreted as a boolean.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        message = "Cannot coerce string value to bool."
        raise TypeError(message)
    if isinstance(value, (int, float)):
        return bool(value)
    message = "Cannot coerce value to bool."
    raise TypeError(message)


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
    environment: Mapping[str, str],
) -> tuple[Any, tuple[DiagnosticDetail, ...]]:
    """Validate configuration using a dataclass validator.

    Args:
        data: Mapping produced by discovery.
        validator: Dataclass type describing expected configuration fields.
        environment: Environment mapping used for validator overrides.

    Returns:
        Pair containing the dataclass instance and associated diagnostics.

    Raises:
        _ValidationFailureError: If required fields are missing or coercion
        fails.
    """
    field_definitions = tuple(fields(validator))
    field_names = [definition.name for definition in field_definitions]
    merged_data = dict(data)
    overrides, override_diagnostics = resolve_validator_overrides(
        validator,
        field_names=field_names,
        environment=environment,
    )
    if overrides:
        merged_data.update(overrides)

    payload: dict[str, Any] = {}
    errors: list[str] = []
    type_hints = get_type_hints(validator)

    for field in field_definitions:
        name = field.name
        has_default = (
            field.default is not MISSING
            or getattr(field, "default_factory", MISSING) is not MISSING
        )

        if name not in merged_data:
            if has_default:
                continue
            errors.append(f"{name}: missing required field")
            continue

        value = merged_data[name]
        annotation = type_hints.get(name, field.type)
        try:
            payload[name] = _coerce_for_annotation(value, annotation)
        except (TypeError, ValueError) as exc:
            error_message = (
                f"{name}: expected {_describe_annotation(annotation)}, "
                f"received {type(value).__name__} ({exc})"
            )
            errors.append(error_message)

    if errors:
        detail = DiagnosticDetail(
            stage="validation.dataclass",
            message="Dataclass validation failed.",
            data={"errors": tuple(errors)},
        )
        raise _ValidationFailureError(detail, diagnostics=override_diagnostics)

    try:
        instance = validator(**payload)
    except TypeError as exc:
        detail = DiagnosticDetail(
            stage="validation.dataclass",
            message="Dataclass instantiation failed.",
            data={"error": str(exc)},
        )
        raise _ValidationFailureError(
            detail,
            diagnostics=override_diagnostics,
        ) from exc

    detail = DiagnosticDetail(
        stage="validation.dataclass",
        message="Validated configuration using dataclass schema.",
        data={"fields": tuple(payload)},
    )
    diagnostics = (*tuple(override_diagnostics), detail)
    return instance, diagnostics


def _coerce_for_annotation(value: Any, annotation: Any) -> Any:
    """Coerce a value according to a type annotation.

    Args:
        value: Value to coerce.
        annotation: Annotation describing the expected type or union.

    Returns:
        Value coerced according to the annotation rules.

    Raises:
        TypeError: If the value cannot satisfy any branch of an optional
        annotation.
        ValueError: If coercion fails for simple types.
    """
    origin = get_origin(annotation)
    if origin is None:
        if annotation in {Any, object} or annotation is None:
            return value
        if isinstance(annotation, type):
            return _coerce_value(value, annotation)
        return value

    if origin is Union:
        args = get_args(annotation)
        if type(None) in args and value is None:
            return None
        for arg in args:
            if arg is type(None):
                continue
            try:
                return _coerce_for_annotation(value, arg)
            except (TypeError, ValueError):
                continue
        message = "Value does not match any allowed Union variant."
        raise ValueError(message)

    return value


def _describe_annotation(annotation: Any) -> str:
    """Return a human-readable description of a type annotation.

    Args:
        annotation: Annotation to describe.

    Returns:
        Human-readable string describing the annotation.
    """
    origin = get_origin(annotation)
    if origin is None:
        return getattr(annotation, "__name__", str(annotation))

    if origin is Union:
        parts = ", ".join(_describe_annotation(arg) for arg in get_args(annotation))
        return f"Union[{parts}]"

    return str(annotation)


def _is_pydantic_validator(validator: Any) -> bool:
    """Determine whether the validator is a Pydantic model.

    Args:
        validator: Validator descriptor under inspection.

    Returns:
        Boolean indicating whether the validator is a Pydantic model.
    """
    if _PydanticBaseModel is None or not isinstance(validator, type):
        return False
    return issubclass(validator, _PydanticBaseModel)


def _get_pydantic_field_names(validator: type) -> list[str]:
    """Return the declared field names for a Pydantic model."""
    if hasattr(validator, "model_fields"):
        fields_attr = validator.model_fields
        if isinstance(fields_attr, Mapping):
            return list(fields_attr)
        return list(fields_attr.keys())  # pragma: no cover - defensive branch

    if hasattr(validator, "__fields__"):
        fields_attr = validator.__fields__
        if isinstance(fields_attr, Mapping):
            return list(fields_attr)
        return list(fields_attr.keys())  # pragma: no cover - defensive branch

    return []


def _validate_pydantic(
    data: Mapping[str, Any],
    validator: type,
    environment: Mapping[str, str],
) -> tuple[Any, tuple[DiagnosticDetail, ...]]:
    """Validate configuration using a Pydantic model.

    Args:
        data: Mapping produced by discovery.
        validator: Pydantic model type supplied by the caller.
        environment: Environment mapping used for validator overrides.

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
    field_names = _get_pydantic_field_names(validator)
    merged_data = dict(data)
    overrides, override_diagnostics = resolve_validator_overrides(
        validator,
        field_names=field_names,
        environment=environment,
    )
    if overrides:
        merged_data.update(overrides)

    try:
        instance = validator(**merged_data)
    except _PydanticValidationError as exc:  # type: ignore[misc]
        detail = DiagnosticDetail(
            stage="validation.pydantic",
            message="Pydantic validation failed.",
            data={"errors": exc.errors() if hasattr(exc, "errors") else str(exc)},
        )
        raise _ValidationFailureError(
            detail,
            diagnostics=override_diagnostics,
        ) from exc

    detail = DiagnosticDetail(
        stage="validation.pydantic",
        message="Validated configuration using Pydantic model.",
        data={"model": f"{validator.__module__}.{validator.__qualname__}"},
    )
    diagnostics = (*tuple(override_diagnostics), detail)
    return instance, diagnostics
