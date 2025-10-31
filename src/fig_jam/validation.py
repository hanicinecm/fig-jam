"""Validation pipeline for fig_jam configuration data."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import MISSING, dataclass, fields, is_dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Union, get_args, get_origin, get_type_hints

from fig_jam.discovery import DiscoveryResult
from fig_jam.exceptions import DiagnosticDetail

try:
    from pydantic import BaseModel as _PydanticBaseModel
    from pydantic import ValidationError as _PydanticValidationError
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    _PydanticBaseModel = None  # type: ignore[assignment]
    _PydanticValidationError = None  # type: ignore[assignment]

_SEQUENCE_EXCLUSIONS = (str, bytes, bytearray)


@dataclass(frozen=True)
class ValidationCandidate:
    """Represents a candidate configuration after validation."""

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
    """Aggregated validation outcome for downstream consumption by the loader."""

    candidates: Sequence[ValidationCandidate]

    def __post_init__(self) -> None:
        """Freeze the candidate sequence to guarantee deterministic ordering."""
        object.__setattr__(self, "candidates", tuple(self.candidates))


def validate_candidates(
    discovery_result: DiscoveryResult,
    validator: Any,
) -> ValidationResult:
    """Validate discovery results using the supplied validator."""
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
            validated, new_diagnostics = _run_validation(candidate.data, validator)
        except _ValidationFailureError as exc:
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

    def __init__(self, diagnostic: DiagnosticDetail) -> None:
        """Store the diagnostic detail associated with the failure."""
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


def _run_validation(
    data: Mapping[str, Any],
    validator: Any,
) -> tuple[Any, tuple[DiagnosticDetail, ...]]:
    """Run the validator against the provided mapping."""
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
        return _validate_dataclass(data, validator)

    if _is_pydantic_validator(validator):
        return _validate_pydantic(data, validator)

    message = "Unsupported validator type."
    raise TypeError(message)


def _is_string_sequence_validator(validator: Any) -> bool:
    """Determine whether the validator is a sequence of strings."""
    if isinstance(validator, _SEQUENCE_EXCLUSIONS):
        return False
    if isinstance(validator, Sequence):
        return all(isinstance(item, str) for item in validator)
    return False


def _validate_key_list(
    data: Mapping[str, Any], validator: Sequence[str]
) -> tuple[Mapping[str, Any], tuple[DiagnosticDetail, ...]]:
    """Validate configuration using a list of keys."""
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
    """Validate configuration with a mapping of keys to types."""
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
    """Coerce a value to the target type with helpful error messaging."""
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
    """Coerce a value into a boolean using human-friendly rules."""
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
    """Determine whether the validator is a dataclass type."""
    return isinstance(validator, type) and is_dataclass(validator)


def _validate_dataclass(
    data: Mapping[str, Any], validator: type
) -> tuple[Any, tuple[DiagnosticDetail, ...]]:
    """Validate configuration using a dataclass validator."""
    payload: dict[str, Any] = {}
    errors: list[str] = []

    type_hints = get_type_hints(validator)

    for field in fields(validator):
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


def _coerce_for_annotation(value: Any, annotation: Any) -> Any:
    """Coerce a value according to a type annotation."""
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
    """Return a human-readable description of a type annotation."""
    origin = get_origin(annotation)
    if origin is None:
        return getattr(annotation, "__name__", str(annotation))

    if origin is Union:
        parts = ", ".join(_describe_annotation(arg) for arg in get_args(annotation))
        return f"Union[{parts}]"

    return str(annotation)


def _is_pydantic_validator(validator: Any) -> bool:
    """Determine whether the validator is a Pydantic model."""
    if _PydanticBaseModel is None or not isinstance(validator, type):
        return False
    return issubclass(validator, _PydanticBaseModel)


def _validate_pydantic(
    data: Mapping[str, Any], validator: type
) -> tuple[Any, tuple[DiagnosticDetail, ...]]:
    """Validate configuration using a Pydantic model."""
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
