"""Apply environment variable overrides to discovered configuration data.

The overrides layer decodes FIG_JAM-prefixed environment variables, merges
them into discovery results, and surfaces diagnostics describing successes or
failures. This module couples directly to `fig_jam.loader` and
`fig_jam.exceptions` while remaining agnostic to validators or caching.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, MutableMapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, NamedTuple, cast

from fig_jam.exceptions import DiagnosticDetail

_ENV_PREFIX = "FIG_JAM__"


class _OverrideInstruction(NamedTuple):
    """Represents a parsed override instruction."""

    environment_key: str
    path: tuple[str, ...]
    value: str


@dataclass(frozen=True)
class OverrideOutcome:
    """Outcome of applying overrides to a mapping."""

    data: Mapping[str, Any] | None
    diagnostics: tuple[DiagnosticDetail, ...]
    success: bool
    signature: tuple[tuple[str, str], ...]


def apply_overrides(
    data: Mapping[str, Any],
    *,
    section: str | None,
    environment: Mapping[str, str] | None = None,
) -> OverrideOutcome:
    """Apply FIG_JAM environment overrides to the supplied mapping.

    Args:
        data: Parsed configuration mapping targeted for overrides.
        section: Optional section name that scopes applicable overrides.
        environment: Mapping of environment variables to inspect. Defaults to
            ``os.environ`` when omitted.

    Returns:
        Structured outcome including the merged mapping, diagnostics, success
        flag, and override signature.
    """
    env_mapping = environment or os.environ
    instructions = tuple(_iter_instructions(env_mapping, section=section))
    signature = tuple(
        sorted(
            (instruction.environment_key, instruction.value)
            for instruction in instructions
        )
    )
    if not instructions:
        return OverrideOutcome(
            data=data,
            diagnostics=(),
            success=True,
            signature=signature,
        )

    mutable = _clone_mapping(data)
    diagnostics: list[DiagnosticDetail] = []
    success = True

    for instruction in instructions:
        applied, detail = _apply_instruction_with_diagnostics(
            mutable,
            instruction,
        )
        diagnostics.append(detail)
        if not applied:
            success = False

    if not success:
        return OverrideOutcome(
            data=None,
            diagnostics=tuple(diagnostics),
            success=False,
            signature=signature,
        )

    frozen = _freeze_mapping(mutable)
    return OverrideOutcome(
        data=frozen,
        diagnostics=tuple(diagnostics),
        success=True,
        signature=signature,
    )


class OverrideError(Exception):
    """Base exception for override failures."""

    def __init__(self, message: str, *, data: Mapping[str, Any] | None = None) -> None:
        """Initialise the error with optional context data."""
        super().__init__(message)
        self.data = dict(data or {})


class OverrideUnsupportedError(OverrideError):
    """Raised when attempting to override a non-mapping path."""


def _iter_instructions(
    environment: Mapping[str, str], *, section: str | None
) -> Iterator[_OverrideInstruction]:
    """Yield override instructions derived from environment variables.

    Args:
        environment: Mapping of environment variables to inspect.
        section: Optional section name that filters applicable overrides.

    Yields:
        Parsed override instructions describing the environment key, target
        path, and raw value.
    """
    section_lower = section.lower() if section is not None else None
    for key, value in environment.items():
        normalized_key = key.upper()
        if not normalized_key.startswith(_ENV_PREFIX):
            continue

        remainder = key[len(_ENV_PREFIX) :]
        parts = [part for part in remainder.split("__") if part]
        if not parts:
            continue

        path_parts = parts
        if section_lower is not None:
            if parts[0].lower() != section_lower:
                continue
            path_parts = parts[1:]
            if not path_parts:
                continue

        normalized_path = tuple(part.lower() for part in path_parts)
        yield _OverrideInstruction(key, normalized_path, value)


def compute_override_signature(
    section: str | None, environment: Mapping[str, str] | None = None
) -> tuple[tuple[str, str], ...]:
    """Return a deterministic signature for applicable environment overrides.

    Args:
        section: Optional section name to scope overrides.
        environment: Mapping of environment variables to inspect. Defaults to
            ``os.environ`` when omitted.

    Returns:
        Deterministic collection of overrides used to influence the
        configuration, ordered for cache key construction.
    """
    env_mapping = environment or os.environ
    instructions = _iter_instructions(env_mapping, section=section)
    return tuple(
        sorted(
            (instruction.environment_key, instruction.value)
            for instruction in instructions
        )
    )


def _clone_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a shallow recursive copy of a mapping for mutation.

    Args:
        data: Mapping to clone recursively.

    Returns:
        Mutable dictionary suitable for in-place override application.
    """
    cloned: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, Mapping):
            cloned[key] = _clone_mapping(value)
        else:
            cloned[key] = value
    return cloned


def _apply_instruction(
    mutable: MutableMapping[str, Any],
    instruction: _OverrideInstruction,
) -> None:
    """Apply a single override instruction to the mutable mapping.

    Args:
        mutable: Mutable configuration mapping to update.
        instruction: Parsed override instruction describing target path and
            value.

    Raises:
        OverrideUnsupportedError: If the override targets a non-mapping parent
        value.
    """
    current: MutableMapping[str, Any] = mutable
    for segment in instruction.path[:-1]:
        key = _find_matching_key(current, segment)
        if key is None:
            key = segment
            current[key] = {}

        next_value = current[key]
        if isinstance(next_value, Mapping):
            if not isinstance(next_value, MutableMapping):
                next_value = _clone_mapping(next_value)
                current[key] = next_value
        else:
            message = "Cannot apply override to a non-mapping parent."
            raise OverrideUnsupportedError(
                message,
                data={"segment": segment, "path": instruction.path},
            )

        current = cast("MutableMapping[str, Any]", next_value)

    final_segment = instruction.path[-1]
    key = _find_matching_key(current, final_segment) or final_segment
    current[key] = instruction.value


def _apply_instruction_with_diagnostics(
    mutable: MutableMapping[str, Any],
    instruction: _OverrideInstruction,
) -> tuple[bool, DiagnosticDetail]:
    """Apply an override instruction and return success metadata.

    Args:
        mutable: Mutable configuration mapping to update.
        instruction: Parsed override instruction.

    Returns:
        Pair containing a success flag and diagnostic detail describing the
        outcome.
    """
    try:
        _apply_instruction(mutable, instruction)
    except (OverrideError, OverrideUnsupportedError) as exc:
        detail = DiagnosticDetail(
            stage="overrides.merge",
            message=str(exc),
            data={"override": instruction.environment_key, **exc.data},
        )
        return False, detail

    detail = DiagnosticDetail(
        stage="overrides.merge",
        message="Applied environment override.",
        data={
            "override": instruction.environment_key,
            "path": instruction.path,
        },
    )
    return True, detail


def _find_matching_key(mapping: Mapping[str, Any], segment: str) -> str | None:
    """Locate an existing key using case-insensitive matching.

    Args:
        mapping: Mapping whose keys are inspected.
        segment: Segment value from the override instruction.

    Returns:
        Matching key from the mapping when present, otherwise ``None``.
    """
    segment_lower = segment.lower()
    for key in mapping:
        if isinstance(key, str) and key.lower() == segment_lower:
            return key
    return None


def _freeze_mapping(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Freeze a mapping recursively using mapping proxies.

    Args:
        data: Mapping to freeze.

    Returns:
        Immutable mapping proxy mirroring the original structure.
    """
    frozen: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, Mapping):
            frozen[key] = _freeze_mapping(value)
        else:
            frozen[key] = value
    return MappingProxyType(frozen)
