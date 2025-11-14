"""Discover configuration candidates prior to validation.

This module walks file system locations, invokes parsers registered in
`fig_jam.parsers`, and extracts optional sections before validation. It is
consumed exclusively by `fig_jam.loader` and therefore couples to the parser
registry and diagnostic structures from `fig_jam.exceptions`. Public exports
include the `discover_candidates` function and its supporting data classes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from fig_jam.exceptions import DiagnosticDetail
from fig_jam.parsers import get_registered_parser, iter_registered_suffixes
from fig_jam.pipeline import PipelineBatch, PipelineCandidate
from fig_jam.utils.mappings import freeze_mapping


def discover_candidates(path: Path, section: str | None) -> PipelineBatch:
    """Enumerate and parse configuration candidates for downstream validation.

    Args:
        path: Canonical path to a configuration file or directory.
        section: Optional section key to extract from successful candidates.

    Returns:
        Immutable record of all attempted candidates and their diagnostics.
    """
    if not path.exists():
        detail = DiagnosticDetail(
            stage="discovery.enumeration",
            message="Configured path does not exist.",
            data={"path": str(path)},
        )
        candidate = PipelineCandidate(
            source_path=path,
            data=None,
            diagnostics=(detail,),
        )
        return PipelineBatch((candidate,))

    if path.is_file():
        candidate = _evaluate_candidate(path, section)
        return PipelineBatch((candidate,))

    if path.is_dir():
        candidates = _evaluate_directory(path, section)
        return PipelineBatch(candidates)

    # Handle failure case where path is neither file nor directory
    detail = DiagnosticDetail(
        stage="discovery.enumeration",
        message="Configured path is neither a file nor a directory.",
        data={"path": str(path)},
    )
    candidate = PipelineCandidate(
        source_path=path,
        data=None,
        diagnostics=(detail,),
    )
    return PipelineBatch((candidate,))


def _evaluate_directory(
    directory: Path,
    section: str | None,
) -> tuple[PipelineCandidate, ...]:
    """Evaluate all registered candidates within the provided directory.

    Args:
        directory: Directory to probe for configuration files.
        section: Optional section key to extract from parsed results.

    Returns:
        Sequence of discovery candidates representing each probed file or a
        synthetic candidate when no supported files exist.
    """
    suffixes = {suffix.lower() for suffix in iter_registered_suffixes()}
    candidates = [
        _evaluate_candidate(candidate_path, section)
        for candidate_path in sorted(directory.iterdir())
        if candidate_path.is_file() and candidate_path.suffix.lower() in suffixes
    ]

    if candidates:
        return tuple(candidates)

    # Handle case where no supported files were found
    detail = DiagnosticDetail(
        stage="discovery.enumeration",
        message="No configuration files with supported extensions were found.",
        data={
            "path": str(directory),
            "supported_extensions": tuple(sorted(suffixes)),
        },
    )
    candidate = PipelineCandidate(
        source_path=directory,
        data=None,
        diagnostics=(detail,),
    )
    return (candidate,)


def _evaluate_candidate(path: Path, section: str | None) -> PipelineCandidate:
    """Parse and optionally extract a section from a candidate file.

    Args:
        path: Path to the configuration file under evaluation.
        section: Optional section key to extract from the parsed mapping.

    Returns:
        Discovery result populated with parser diagnostics and extracted data
        when successful.
    """
    parser = get_registered_parser(path.suffix)
    if parser is None:
        detail = DiagnosticDetail(
            stage="discovery.parsers",
            message="No parser is registered for the file extension.",
            data={"path": str(path), "extension": path.suffix.lower()},
        )
        return PipelineCandidate(
            source_path=path,
            data=None,
            diagnostics=(detail,),
        )

    result = parser(path)
    candidate = PipelineCandidate(
        source_path=path,
        data=result.data if result.success else None,
        diagnostics=result.diagnostics,
    )
    if not result.success or candidate.data is None:
        return candidate

    mapping = cast("Mapping[str, Any]", candidate.data)
    if section is None:
        return candidate

    section_result = _extract_section(mapping, section, path)
    updated = candidate.append_diagnostics(section_result.diagnostic)
    if section_result.data is None:
        return updated.with_data(None)
    return updated.with_data(section_result.data)


def _extract_section(
    mapping: Mapping[str, Any], section: str, path: Path
) -> _SectionExtraction:
    """Extract a section from the mapping while preserving immutability.

    Args:
        mapping: Parsed configuration mapping.
        section: Section key to extract.
        path: Path to the current configuration file for diagnostic context.

    Returns:
        Structured result containing the extracted mapping and associated
        diagnostic detail.
    """
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

    frozen = freeze_mapping(value)
    detail = DiagnosticDetail(
        stage="discovery.section",
        message=f"Section '{section}' extracted successfully.",
        data={"path": str(path), "section": section},
    )
    return _SectionExtraction(data=frozen, diagnostic=detail)


@dataclass(frozen=True)
class _SectionExtraction:
    """Represents the outcome of extracting a section.

    Attributes:
        data: Extracted mapping when available.
        diagnostic: Diagnostic detail describing the extraction attempt.
    """

    data: Mapping[str, Any] | None
    diagnostic: DiagnosticDetail
