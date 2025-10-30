"""Domain-specific exceptions and diagnostics structures for fig_jam."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class DiagnosticDetail:
    """Represents a diagnostic message describing a pipeline stage outcome."""

    stage: str
    message: str
    data: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Freeze the diagnostic payload to ensure immutability."""
        if self.data is not None and not isinstance(self.data, MappingProxyType):
            object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def as_dict(self) -> dict[str, Any]:
        """Serialize the diagnostic detail into a dictionary."""
        payload: dict[str, Any] = {"stage": self.stage, "message": self.message}
        if self.data is not None:
            payload["data"] = dict(self.data)
        return payload


@dataclass(frozen=True)
class CandidateDiagnostic:
    """Aggregated diagnostics associated with a configuration candidate."""

    path: Path
    diagnostics: Sequence[DiagnosticDetail] = field(default_factory=tuple)
    data_preview: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Freeze diagnostics and data preview for deterministic reporting."""
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.data_preview is not None and not isinstance(
            self.data_preview,
            MappingProxyType,
        ):
            object.__setattr__(
                self,
                "data_preview",
                MappingProxyType(dict(self.data_preview)),
            )

    def as_dict(self) -> dict[str, Any]:
        """Serialize candidate diagnostics for structured reporting."""
        payload: dict[str, Any] = {
            "path": str(self.path),
            "diagnostics": [detail.as_dict() for detail in self.diagnostics],
        }
        if self.data_preview is not None:
            payload["data_preview"] = dict(self.data_preview)
        return payload


@dataclass(frozen=True)
class RemediationHint:
    """Actionable remediation guidance accompanying an exception."""

    summary: str
    command: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialize the remediation hint into a dictionary."""
        payload: dict[str, Any] = {"summary": self.summary}
        if self.command:
            payload["command"] = self.command
        return payload


class FigJamError(Exception):
    """Base class for fig_jam exceptions with remediation metadata."""

    summary: str
    diagnostics: tuple[DiagnosticDetail, ...]
    remediation: tuple[RemediationHint, ...]
    context: Mapping[str, Any]

    def __init__(
        self,
        summary: str,
        *,
        diagnostics: Sequence[DiagnosticDetail] | None = None,
        remediation: Sequence[RemediationHint] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        """Set up the error with optional diagnostics, remediation, and context."""
        super().__init__(summary)
        self.summary = summary
        self.diagnostics = tuple(diagnostics or ())
        self.remediation = tuple(remediation or ())
        self.context = MappingProxyType(dict(context or {}))

    def __str__(self) -> str:
        """Render the exception summary along with remediation hints."""
        parts = [self.summary]
        if self.remediation:
            parts.append("")
            parts.append("Remediation:")
            for hint in self.remediation:
                if hint.command:
                    parts.append(f"- {hint.summary} (e.g. `{hint.command}`)")
                else:
                    parts.append(f"- {hint.summary}")
        return "\n".join(parts)

    def as_dict(self) -> dict[str, Any]:
        """Serialize the exception metadata into a dictionary."""
        payload: dict[str, Any] = {"summary": self.summary}
        if self.context:
            payload["context"] = dict(self.context)
        if self.diagnostics:
            payload["diagnostics"] = [detail.as_dict() for detail in self.diagnostics]
        if self.remediation:
            payload["remediation"] = [hint.as_dict() for hint in self.remediation]
        return payload


class DependencyUnavailableError(FigJamError):
    """Raised when an optional dependency required for a feature is missing."""

    dependency: str
    extras: tuple[str, ...]
    reason: str | None

    def __init__(
        self,
        dependency: str,
        *,
        reason: str | None = None,
        extras: Iterable[str] | None = None,
        remediation: Sequence[RemediationHint] | None = None,
    ) -> None:
        """Describe a missing optional dependency and remediation instructions."""
        base_summary = f"Optional dependency '{dependency}' is not available."
        extras_tuple = tuple(extras or ())

        default_hints = [
            RemediationHint(
                summary=f"Install {dependency} using uv",
                command=f"uv add {dependency}",
            ),
            RemediationHint(
                summary=f"Install {dependency} using pip",
                command=f"pip install {dependency}",
            ),
        ]
        if remediation:
            default_hints.extend(remediation)

        context: dict[str, Any] = {"dependency": dependency}
        if extras_tuple:
            context["extras"] = extras_tuple
        if reason:
            context["reason"] = reason

        super().__init__(
            base_summary,
            remediation=default_hints,
            context=context,
        )
        self.dependency = dependency
        self.extras = extras_tuple
        self.reason = reason


class ConfigSourceNotFoundError(FigJamError):
    """Raised when no configuration sources are discovered."""

    attempted_candidates: tuple[CandidateDiagnostic, ...]
    supported_extensions: tuple[str, ...]
    validator_summary: str | None
    sample_config: Mapping[str, Any] | None

    def __init__(
        self,
        *,
        attempted_candidates: Sequence[CandidateDiagnostic],
        supported_extensions: Iterable[str],
        validator_summary: str | None = None,
        sample_config: Mapping[str, Any] | None = None,
        remediation: Sequence[RemediationHint] | None = None,
    ) -> None:
        """Report that no configuration sources were successfully discovered."""
        summary = "No configuration sources matched the requested criteria."

        extensions = tuple(sorted({ext.lower() for ext in supported_extensions}))
        context: dict[str, Any] = {
            "attempted_paths": [
                str(candidate.path) for candidate in attempted_candidates
            ],
            "supported_extensions": extensions,
        }
        if validator_summary:
            context["validator"] = validator_summary
        if sample_config is not None:
            context["sample_config"] = dict(sample_config)

        hints = list(remediation or [])
        if not hints:
            hints.append(
                RemediationHint(
                    summary="Create a configuration file using a supported extension.",
                ),
            )

        diagnostics = tuple(
            detail
            for candidate in attempted_candidates
            for detail in candidate.diagnostics
        )

        super().__init__(
            summary,
            diagnostics=diagnostics,
            remediation=hints,
            context=context,
        )
        self.attempted_candidates = tuple(attempted_candidates)
        self.supported_extensions = extensions
        self.validator_summary = validator_summary
        self.sample_config = (
            MappingProxyType(dict(sample_config)) if sample_config is not None else None
        )


class ConfigSourceAmbiguityError(FigJamError):
    """Raised when multiple configuration sources satisfy the requested criteria."""

    matching_candidates: tuple[CandidateDiagnostic, ...]

    def __init__(
        self,
        *,
        matching_candidates: Sequence[CandidateDiagnostic],
        remediation: Sequence[RemediationHint] | None = None,
    ) -> None:
        """Report ambiguity when several candidates satisfy the filter."""
        summary = "Multiple configuration sources matched the requested criteria."

        context = {
            "matching_paths": [
                str(candidate.path) for candidate in matching_candidates
            ],
        }
        hints = list(remediation or [])
        if not hints:
            hints.append(
                RemediationHint(
                    summary=(
                        "Provide a more precise path or restrict the search parameters."
                    ),
                ),
            )

        diagnostics = tuple(
            detail
            for candidate in matching_candidates
            for detail in candidate.diagnostics
        )

        super().__init__(
            summary,
            diagnostics=diagnostics,
            remediation=hints,
            context=context,
        )
        self.matching_candidates = tuple(matching_candidates)


class ConfigValidationError(FigJamError):
    """Raised when discovered configuration data fails validation."""

    failing_candidates: tuple[CandidateDiagnostic, ...]
    validator_summary: str | None

    def __init__(
        self,
        *,
        failing_candidates: Sequence[CandidateDiagnostic],
        validator_summary: str | None = None,
        remediation: Sequence[RemediationHint] | None = None,
    ) -> None:
        """Report validation errors for one or more configuration candidates."""
        summary = "Configuration validation failed for the discovered sources."

        context: dict[str, Any] = {
            "failing_paths": [str(candidate.path) for candidate in failing_candidates],
        }
        if validator_summary:
            context["validator"] = validator_summary

        hints = list(remediation or [])
        if not hints:
            hints.append(
                RemediationHint(
                    summary=(
                        "Adjust the configuration to satisfy validator requirements."
                    ),
                ),
            )
            hints.append(
                RemediationHint(
                    summary="Review the validation errors for each candidate.",
                ),
            )

        diagnostics = tuple(
            detail
            for candidate in failing_candidates
            for detail in candidate.diagnostics
        )

        super().__init__(
            summary,
            diagnostics=diagnostics,
            remediation=hints,
            context=context,
        )
        self.failing_candidates = tuple(failing_candidates)
        self.validator_summary = validator_summary
