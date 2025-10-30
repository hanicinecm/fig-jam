"""Configuration discovery stage for fig_jam."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fig_jam.exceptions import DiagnosticDetail


@dataclass(frozen=True)
class DiscoveryCandidate:
    """Represents a single candidate configuration file."""

    path: Path
    data: Mapping[str, Any] | None
    diagnostics: Sequence[DiagnosticDetail]

    def __post_init__(self) -> None:
        """Ensure diagnostics and data use immutable containers."""
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.data is not None and not isinstance(self.data, MappingProxyType):
            object.__setattr__(self, "data", MappingProxyType(dict(self.data)))


@dataclass(frozen=True)
class DiscoveryResult:
    """Aggregated discovery outcome containing all probed candidates."""

    candidates: Sequence[DiscoveryCandidate]

    def __post_init__(self) -> None:
        """Freeze the candidate sequence to guarantee immutability."""
        object.__setattr__(self, "candidates", tuple(self.candidates))


def discover_candidates(path: Path | None, section: str | None) -> DiscoveryResult:
    """Enumerate and parse configuration candidates for downstream validation."""
    message = "Discovery pipeline will be implemented in Task 3."
    raise NotImplementedError(message)
