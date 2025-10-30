"""Validation pipeline for fig_jam configuration data."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from fig_jam.exceptions import DiagnosticDetail


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
    discovery_result: Any,
    validator: Any,
) -> ValidationResult:
    """Validate discovery results using the supplied validator."""
    message = "Validation pipeline will be implemented in Task 5."
    raise NotImplementedError(message)
