"""Environment variable overrides for fig_jam."""

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
    """Apply FIG_JAM environment overrides to the supplied mapping."""
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
    """Yield override instructions derived from environment variables."""
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
    """Return a deterministic signature for applicable environment overrides."""
    env_mapping = environment or os.environ
    instructions = _iter_instructions(env_mapping, section=section)
    return tuple(
        sorted(
            (instruction.environment_key, instruction.value)
            for instruction in instructions
        )
    )


def _clone_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep-ish mutable copy of the mapping."""
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
    """Apply a single override instruction to the mutable mapping."""
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
    """Apply an override instruction and return success metadata."""
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
    """Locate an existing key using case-insensitive matching."""
    segment_lower = segment.lower()
    for key in mapping:
        if isinstance(key, str) and key.lower() == segment_lower:
            return key
    return None


def _freeze_mapping(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Freeze a mapping recursively using mapping proxies."""
    frozen: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, Mapping):
            frozen[key] = _freeze_mapping(value)
        else:
            frozen[key] = value
    return MappingProxyType(frozen)
