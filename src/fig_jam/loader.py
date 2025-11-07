"""Compose the end-to-end configuration loading workflow.

This module orchestrates discovery, validation, validator-defined overrides,
and error shaping. Its public API `get_config` represents the package's primary
entry point. The module couples to `fig_jam.discovery`, `fig_jam.validation`,
`fig_jam.exceptions`, and `fig_jam.parsers` to connect
the pipeline stages.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from fig_jam.discovery import discover_candidates
from fig_jam.exceptions import (
    CandidateDiagnostic,
    ConfigSourceAmbiguityError,
    ConfigSourceNotFoundError,
    ConfigValidationError,
)
from fig_jam.overrides import override_candidates
from fig_jam.parsers import iter_registered_suffixes
from fig_jam.pipeline import PipelineBatch, PipelineCandidate
from fig_jam.utils.paths import canonicalize_path
from fig_jam.validation import validate_candidates

logger = logging.getLogger(__name__)


def get_config(
    path: Path | None = None,
    section: str | None = None,
    validator: Any | None = None,
) -> Any:
    """Load configuration data according to the provided parameters.

    Args:
        path: Explicit configuration file or directory to probe. Defaults to
            the user's home directory when omitted.
        section: Optional section key to extract from candidate mappings.
        validator: Optional schema or callable used to validate the resulting
            configuration.

    Returns:
        Validated configuration object whose structure depends on the supplied
        validator.

    Raises:
        ConfigSourceNotFoundError: When no viable configuration is discovered.
        ConfigSourceAmbiguityError: When multiple candidates pass validation.
        ConfigValidationError: When candidates are discovered but fail
            validation.
    """
    canonical_path = canonicalize_path(path)
    environment = os.environ
    logger.debug(
        "Loading configuration",
        extra={
            "path": str(canonical_path),
            "section": section,
            "validator": _describe_validator(validator),
        },
    )

    return _load_config_internal(
        canonical_path=canonical_path,
        section=section,
        validator=validator,
        environment=environment,
    )


def _load_config_internal(
    *,
    canonical_path: Path,
    section: str | None,
    validator: Any | None,
    environment: Mapping[str, str],
) -> Any:
    """Run the configuration pipeline stages in order.

    Args:
        canonical_path: Canonical path derived from user input.
        section: Optional section key for extraction.
        validator: Optional validator supplied by the caller.
        environment: Environment mapping from which overrides are derived.

    Returns:
        Validated configuration payload produced by downstream stages.

    Raises:
        ConfigSourceNotFoundError: When no viable configuration is discovered.
        ConfigSourceAmbiguityError: When multiple candidates pass validation.
        ConfigValidationError: When candidates fail validation.
    """
    discovery_batch = discover_candidates(canonical_path, section)
    logger.debug(
        "Discovery completed",
        extra={"path": str(canonical_path), "candidate_count": len(discovery_batch)},
    )

    overrides_batch = override_candidates(
        discovery_batch,
        validator,
        environment=environment,
    )

    override_events = sum(
        1
        for candidate in overrides_batch
        for detail in candidate.diagnostics
        if detail.stage.startswith("overrides.")
    )
    if override_events:
        logger.debug(
            "Overrides applied",
            extra={
                "path": str(canonical_path),
                "override_events": override_events,
            },
        )

    validation_batch = validate_candidates(
        overrides_batch,
        validator,
    )
    successes = sum(1 for candidate in validation_batch if candidate.data is not None)
    logger.debug(
        "Validation completed",
        extra={
            "path": str(canonical_path),
            "successes": successes,
        },
    )

    return _finalize_result(
        validation_batch,
        validator=validator,
    )


def _finalize_result(
    validation_batch: PipelineBatch,
    *,
    validator: Any | None,
) -> Any:
    """Derive the final return value or raise a descriptive exception.

    Args:
        validation_batch: Validation outcomes for all candidates.
        validator: Validator provided by the caller.

    Returns:
        Final configuration object when exactly one candidate succeeds.

    Raises:
        ConfigSourceAmbiguityError: When more than one candidate succeeds.
        ConfigValidationError: When candidates fail validation.
        ConfigSourceNotFoundError: When no candidates pass discovery or
            validation.
    """
    successful = [
        candidate for candidate in validation_batch if candidate.data is not None
    ]

    if len(successful) == 1:
        return successful[0].data

    diagnostics = tuple(
        _build_candidate_diagnostic(candidate) for candidate in validation_batch
    )

    if len(successful) > 1:
        raise ConfigSourceAmbiguityError(matching_candidates=diagnostics)

    validation_failures = [
        diag
        for diag in diagnostics
        if any(detail.stage.startswith("validation.") for detail in diag.diagnostics)
    ]

    if validation_failures:
        raise ConfigValidationError(
            failing_candidates=validation_failures,
            validator_summary=_describe_validator(validator),
        )

    raise ConfigSourceNotFoundError(
        attempted_candidates=diagnostics,
        supported_extensions=tuple(iter_registered_suffixes()),
        validator_summary=_describe_validator(validator),
        sample_config=_build_sample_config(validator),
    )


def _build_candidate_diagnostic(candidate: PipelineCandidate) -> CandidateDiagnostic:
    """Convert a validation candidate into a diagnostic record.

    Args:
        candidate: Validation candidate to summarize.

    Returns:
        Candidate diagnostic containing path, diagnostics, and data preview.
    """
    data_preview: Mapping[str, Any] | None = None
    if isinstance(candidate.data, Mapping):
        data_preview = dict(candidate.data)

    return CandidateDiagnostic(
        path=candidate.source_path,
        diagnostics=candidate.diagnostics,
        data_preview=data_preview,
    )


def _describe_validator(validator: Any | None) -> str | None:
    """Provide a human-readable description of the validator.

    Args:
        validator: Validator descriptor supplied by the caller.

    Returns:
        Human-readable summary string or ``None`` when no validator was
        provided.
    """
    if validator is None:
        return None

    if isinstance(validator, Mapping):
        parts = [
            f"{key}: {value.__name__}"
            for key, value in validator.items()
            if isinstance(value, type)
        ]
        return f"dict[{', '.join(parts)}]" if parts else "dict"

    if isinstance(validator, Sequence) and not isinstance(
        validator,
        (str, bytes, bytearray),
    ):
        return f"keys[{', '.join(str(item) for item in validator)}]"

    if isinstance(validator, type):
        return f"{validator.__module__}.{validator.__qualname__}"

    return str(validator)


def _build_sample_config(validator: Any | None) -> Mapping[str, Any] | None:
    """Generate a sample configuration structure based on the validator.

    Args:
        validator: Validator descriptor to project onto a sample config.

    Returns:
        Example configuration mapping aligned with the validator, or ``None``
        when a sample cannot be inferred.
    """
    if validator is None:
        return None

    if isinstance(validator, Mapping):
        return {
            key: _render_placeholder(value) if isinstance(value, type) else "<value>"
            for key, value in validator.items()
        }

    if isinstance(validator, Sequence) and not isinstance(
        validator,
        (str, bytes, bytearray),
    ):
        return {key: "<value>" for key in validator if isinstance(key, str)}

    if isinstance(validator, type) and is_dataclass(validator):
        return {
            field.name: _render_placeholder(
                field.type if isinstance(field.type, type) else str(field.type)
            )
            for field in fields(validator)
        }

    return None


def _render_placeholder(target: Any) -> str:
    """Render a placeholder string for a type annotation.

    Args:
        target: Target type or annotation representation.

    Returns:
        Placeholder string describing the expected value.
    """
    if isinstance(target, type):
        return f"<{target.__name__}>"
    return f"<{target}>"
