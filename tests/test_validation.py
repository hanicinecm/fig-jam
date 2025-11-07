"""Tests for the validation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar

import pytest

from fig_jam.discovery import DiscoveryCandidate, DiscoveryResult
from fig_jam.exceptions import DiagnosticDetail
from fig_jam.validation import validate_candidates


def _candidate(path: str, data: dict[str, object]) -> DiscoveryCandidate:
    """Create a discovery candidate for validation."""
    return DiscoveryCandidate(
        path=Path(path),
        data=MappingProxyType(data),
        diagnostics=(DiagnosticDetail(stage="parsers.json", message="ok"),),
    )


def test_validate_candidates_without_validator() -> None:
    """Return discovery data unchanged when no validator is supplied."""
    result = DiscoveryResult(
        candidates=(_candidate("config.json", {"feature": "fig"}),),
    )

    validation = validate_candidates(result, validator=None, environment={})

    candidate = validation.candidates[0]
    assert candidate.data is not None
    assert dict(candidate.data) == {"feature": "fig"}
    assert candidate.diagnostics[-1].stage == "validation.none"


def test_validate_candidates_list_validator_missing_key() -> None:
    """Surface diagnostics when required keys are absent."""
    result = DiscoveryResult(
        candidates=(_candidate("config.json", {"host": "db"}),),
    )

    validation = validate_candidates(
        result,
        validator=["host", "port"],
        environment={},
    )

    candidate = validation.candidates[0]
    assert candidate.data is None
    detail = candidate.diagnostics[-1]
    assert detail.stage == "validation.list"
    assert detail.data is not None
    assert detail.data["missing_keys"] == ("port",)


def test_validate_candidates_dict_validator_coercion() -> None:
    """Coerce dictionary values according to the validator mapping."""
    result = DiscoveryResult(
        candidates=(_candidate("config.json", {"port": "5432"}),),
    )

    validation = validate_candidates(
        result,
        validator={"port": int},
        environment={},
    )

    candidate = validation.candidates[0]
    assert candidate.data is not None
    assert candidate.data["port"] == 5432
    detail = candidate.diagnostics[-1]
    assert detail.stage == "validation.dict"


def test_validate_candidates_dataclass_validator() -> None:
    """Validate using a dataclass schema."""

    @dataclass
    class DatabaseConfig:
        host: str
        port: int
        password: str | None = None

    result = DiscoveryResult(
        candidates=(
            _candidate("config.json", {"host": "db", "port": "5432"}),
            _candidate("missing.json", {"host": "db"}),
        ),
    )

    validation = validate_candidates(
        result,
        validator=DatabaseConfig,
        environment={},
    )

    success, failure = validation.candidates
    assert isinstance(success.data, DatabaseConfig)
    assert success.data.port == 5432

    assert failure.data is None
    detail = failure.diagnostics[-1]
    assert detail.stage == "validation.dataclass"
    assert detail.data is not None
    assert "missing required field" in detail.data["errors"][0]


def test_validate_candidates_dataclass_env_override() -> None:
    """Apply environment overrides declared on a dataclass validator."""

    @dataclass
    class DatabaseConfig:
        host: str
        password: str
        __env_overrides__: ClassVar[dict[str, str]] = {"password": "DB_PASSWORD"}

    result = DiscoveryResult(
        candidates=(_candidate("config.json", {"host": "db"}),),
    )

    validation = validate_candidates(
        result,
        validator=DatabaseConfig,
        environment={"DB_PASSWORD": "secret"},
    )

    candidate = validation.candidates[0]
    assert isinstance(candidate.data, DatabaseConfig)
    assert candidate.data.password == "secret"  # noqa: S105
    assert any(
        detail.stage == "validation.overrides" for detail in candidate.diagnostics
    )


def test_validate_candidates_dataclass_invalid_override() -> None:
    """Raise TypeError when dataclass overrides reference unknown fields."""

    @dataclass
    class InvalidConfig:
        host: str
        __env_overrides__: ClassVar[dict[str, str]] = {"missing": "DB_PASSWORD"}

    result = DiscoveryResult(
        candidates=(_candidate("config.json", {"host": "db"}),),
    )

    with pytest.raises(TypeError):
        validate_candidates(
            result,
            validator=InvalidConfig,
            environment={"DB_PASSWORD": "secret"},
        )


def test_validate_candidates_pydantic_env_override() -> None:
    """Apply environment overrides declared on a Pydantic validator."""
    pydantic = pytest.importorskip("pydantic")

    class AppConfig(pydantic.BaseModel):  # type: ignore[attr-defined]
        host: str
        token: str
        __env_overrides__: ClassVar[dict[str, str]] = {"token": "API_TOKEN"}

    result = DiscoveryResult(
        candidates=(_candidate("config.json", {"host": "api"}),),
    )

    validation = validate_candidates(
        result,
        validator=AppConfig,
        environment={"API_TOKEN": "topsecret"},
    )

    candidate = validation.candidates[0]
    assert isinstance(candidate.data, AppConfig)
    assert candidate.data.token == "topsecret"  # noqa: S105
    assert any(
        detail.stage == "validation.overrides" for detail in candidate.diagnostics
    )
