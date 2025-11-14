"""Shared data structures representing candidates flowing through the pipeline."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from pathlib import Path
from typing import Any

from fig_jam.exceptions import DiagnosticDetail
from fig_jam.utils.mappings import freeze_mapping

try:
    from pydantic import BaseModel as _PydanticBaseModel  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    _PydanticBaseModel = None  # type: ignore[assignment]

_SEQUENCE_EXCLUSIONS = (str, bytes, bytearray)


@dataclass(frozen=True)
class PipelineCandidate:
    """Represents a configuration candidate as it moves through the pipeline."""

    source_path: Path
    data: Any | None
    diagnostics: Sequence[DiagnosticDetail]

    def __post_init__(self) -> None:
        """Normalise diagnostics and freeze mapping payloads for immutability."""
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if isinstance(self.data, Mapping):
            object.__setattr__(self, "data", freeze_mapping(self.data))

    def with_data(self, data: Any | None) -> PipelineCandidate:
        """Return a new candidate with updated data."""
        if isinstance(data, Mapping):
            data = freeze_mapping(data)
        return replace(self, data=data)

    def append_diagnostics(
        self,
        *diagnostics: DiagnosticDetail,
    ) -> PipelineCandidate:
        """Return a candidate with additional diagnostics appended."""
        if not diagnostics:
            return self
        merged = (*self.diagnostics, *diagnostics)
        return replace(self, diagnostics=merged)

    def extend_diagnostics(
        self,
        diagnostics: Iterable[DiagnosticDetail],
    ) -> PipelineCandidate:
        """Return a candidate with an iterable of diagnostics appended."""
        diag_tuple = tuple(diagnostics)
        if not diag_tuple:
            return self
        merged = (*self.diagnostics, *diag_tuple)
        return replace(self, diagnostics=merged)


@dataclass(frozen=True)
class PipelineBatch:
    """Container for an ordered collection of pipeline candidates."""

    candidates: Sequence[PipelineCandidate]

    def __post_init__(self) -> None:
        """Ensure the candidate collection is immutable."""
        object.__setattr__(self, "candidates", tuple(self.candidates))

    def __iter__(self) -> Iterator[PipelineCandidate]:
        """Iterate over contained candidates."""
        return iter(self.candidates)

    def __len__(self) -> int:
        """Return the number of candidates in the batch."""
        return len(self.candidates)

    def map(
        self,
        transformer: Callable[[PipelineCandidate], PipelineCandidate],
    ) -> PipelineBatch:
        """Return a new batch with the transformer applied to each candidate."""
        transformed = (transformer(candidate) for candidate in self.candidates)
        return PipelineBatch(tuple(transformed))

    def replace(self, candidates: Iterable[PipelineCandidate]) -> PipelineBatch:
        """Return a new batch with the supplied candidates."""
        return PipelineBatch(tuple(candidates))


def is_string_sequence_validator(validator: Any) -> bool:
    """Return whether the validator is a sequence of strings."""
    if isinstance(validator, _SEQUENCE_EXCLUSIONS):
        return False
    if isinstance(validator, Sequence):
        return all(isinstance(item, str) for item in validator)
    return False


def is_dataclass_validator(validator: Any) -> bool:
    """Return whether the validator represents a dataclass type."""
    return isinstance(validator, type) and is_dataclass(validator)


def get_dataclass_field_names(validator: type[Any]) -> list[str]:
    """Return the declared field names for a dataclass validator."""
    return [field.name for field in fields(validator)]


def is_pydantic_validator(validator: Any) -> bool:
    """Return whether the validator represents a Pydantic model."""
    if _PydanticBaseModel is None or not isinstance(validator, type):
        return False
    return issubclass(validator, _PydanticBaseModel)


def get_pydantic_field_names(validator: type[Any]) -> list[str]:
    """Return the declared field names for a Pydantic model."""
    if hasattr(validator, "model_fields"):
        fields_attr = validator.model_fields
        if isinstance(fields_attr, dict):
            return list(fields_attr)
        return list(fields_attr.keys())  # pragma: no cover - defensive branch

    if hasattr(validator, "__fields__"):
        fields_attr = validator.__fields__
        if isinstance(fields_attr, dict):
            return list(fields_attr)
        return list(fields_attr.keys())  # pragma: no cover - defensive branch

    return []
