"""Tests for validator-defined environment overrides."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pytest

from fig_jam.overrides import resolve_validator_overrides


@dataclass
class SampleConfig:
    """Dataclass used for override resolution tests."""

    host: str
    token: str
    __env_overrides__: ClassVar[dict[str, str]] = {"token": "API_TOKEN"}


def test_resolve_validator_overrides_applies_values() -> None:
    """Resolve environment values declared by the validator."""
    overrides, diagnostics = resolve_validator_overrides(
        SampleConfig,
        field_names=["host", "token"],
        environment={"API_TOKEN": "secret-token"},
    )

    assert overrides == {"token": "secret-token"}
    assert diagnostics
    detail = diagnostics[0]
    assert detail.stage == "validation.overrides"
    assert detail.data == {"field": "token", "environment_variable": "API_TOKEN"}


def test_resolve_validator_overrides_missing_variable() -> None:
    """Skip overrides when environment variable is absent."""
    overrides, diagnostics = resolve_validator_overrides(
        SampleConfig,
        field_names=["host", "token"],
        environment={},
    )

    assert overrides == {}
    assert diagnostics == ()


def test_resolve_validator_overrides_unknown_field() -> None:
    """Raise TypeError when mapping references an unknown field."""

    class BadConfig(SampleConfig):
        __env_overrides__: ClassVar[dict[str, str]] = {"missing": "API_TOKEN"}

    with pytest.raises(TypeError):
        resolve_validator_overrides(
            BadConfig,
            field_names=["host", "token"],
            environment={"API_TOKEN": "secret-token"},
        )


def test_resolve_validator_overrides_non_mapping() -> None:
    """Raise TypeError when __env_overrides__ is not a mapping."""

    class AnotherConfig(SampleConfig):
        __env_overrides__ = "not-a-mapping"  # type: ignore[assignment]

    with pytest.raises(TypeError):
        resolve_validator_overrides(
            AnotherConfig,
            field_names=["host", "token"],
            environment={"API_TOKEN": "secret-token"},
        )
