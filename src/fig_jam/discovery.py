"""Configuration discovery stage for fig_jam."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fig_jam.exceptions import DiagnosticDetail
from fig_jam.parsers import get_registered_parser, iter_registered_suffixes


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
    normalized_path = _normalize_input_path(path)
    if not normalized_path.exists():
        detail = DiagnosticDetail(
            stage="discovery.enumeration",
            message="Configured path does not exist.",
            data={"path": str(normalized_path)},
        )
        candidate = DiscoveryCandidate(
            path=normalized_path, data=None, diagnostics=(detail,)
        )
        return DiscoveryResult(candidates=(candidate,))

    if normalized_path.is_file():
        candidate = _evaluate_candidate(normalized_path, section)
        return DiscoveryResult(candidates=(candidate,))

    if normalized_path.is_dir():
        candidates = _evaluate_directory(normalized_path, section)
        return DiscoveryResult(candidates=candidates)

    detail = DiagnosticDetail(
        stage="discovery.enumeration",
        message="Configured path is neither a file nor a directory.",
        data={"path": str(normalized_path)},
    )
    candidate = DiscoveryCandidate(
        path=normalized_path,
        data=None,
        diagnostics=(detail,),
    )
    return DiscoveryResult(candidates=(candidate,))


def _normalize_input_path(path: Path | None) -> Path:
    """Normalise user supplied path parameters."""
    base = path if path is not None else Path.home()
    expanded = base.expanduser()
    try:
        return expanded.resolve()
    except OSError:
        return expanded


def _evaluate_directory(
    directory: Path,
    section: str | None,
) -> tuple[DiscoveryCandidate, ...]:
    """Evaluate all registered candidates within the provided directory."""
    suffixes = {suffix.lower() for suffix in iter_registered_suffixes()}
    candidates: list[DiscoveryCandidate] = []
    for candidate_path in sorted(directory.iterdir()):
        if not candidate_path.is_file():
            continue
        if candidate_path.suffix.lower() not in suffixes:
            continue
        candidates.append(_evaluate_candidate(candidate_path, section))

    if candidates:
        return tuple(candidates)

    detail = DiagnosticDetail(
        stage="discovery.enumeration",
        message="No configuration files with supported extensions were found.",
        data={
            "path": str(directory),
            "supported_extensions": tuple(sorted(suffixes)),
        },
    )
    candidate = DiscoveryCandidate(path=directory, data=None, diagnostics=(detail,))
    return (candidate,)


def _evaluate_candidate(path: Path, section: str | None) -> DiscoveryCandidate:
    """Parse and optionally extract a section from a candidate file."""
    parser = get_registered_parser(path.suffix)
    if parser is None:
        detail = DiagnosticDetail(
            stage="discovery.parsers",
            message="No parser is registered for the file extension.",
            data={"path": str(path), "extension": path.suffix.lower()},
        )
        return DiscoveryCandidate(path=path, data=None, diagnostics=(detail,))

    result = parser(path)
    diagnostics = list(result.diagnostics)
    if not result.success or result.data is None:
        return DiscoveryCandidate(path=path, data=None, diagnostics=diagnostics)

    mapping = result.data
    if section is None:
        return DiscoveryCandidate(path=path, data=mapping, diagnostics=diagnostics)

    section_result = _extract_section(mapping, section, path)
    diagnostics.append(section_result.diagnostic)
    if section_result.data is None:
        return DiscoveryCandidate(path=path, data=None, diagnostics=diagnostics)
    return DiscoveryCandidate(
        path=path,
        data=section_result.data,
        diagnostics=diagnostics,
    )


def _extract_section(
    mapping: Mapping[str, Any], section: str, path: Path
) -> _SectionExtraction:
    """Extract a section from the mapping while preserving immutability."""
    if section not in mapping:
        detail = DiagnosticDetail(
            stage="discovery.section",
            message=f"Section '{section}' was not found in the configuration.",
            data={"path": str(path), "section": section},
        )
        return _SectionExtraction(data=None, diagnostic=detail)

    value = mapping[section]
    if not isinstance(value, Mapping):
        detail = DiagnosticDetail(
            stage="discovery.section",
            message=f"Section '{section}' is not a mapping and cannot be extracted.",
            data={"path": str(path), "section": section, "type": type(value).__name__},
        )
        return _SectionExtraction(data=None, diagnostic=detail)

    frozen = MappingProxyType(dict(value))
    detail = DiagnosticDetail(
        stage="discovery.section",
        message=f"Section '{section}' extracted successfully.",
        data={"path": str(path), "section": section},
    )
    return _SectionExtraction(data=frozen, diagnostic=detail)


@dataclass(frozen=True)
class _SectionExtraction:
    """Represents the outcome of extracting a section."""

    data: Mapping[str, Any] | None
    diagnostic: DiagnosticDetail
