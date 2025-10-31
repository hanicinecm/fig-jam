"""Tests for the validation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

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

    validation = validate_candidates(result, validator=None)

    candidate = validation.candidates[0]
    assert candidate.data is not None
    assert dict(candidate.data) == {"feature": "fig"}
    assert candidate.diagnostics[-1].stage == "validation.none"


def test_validate_candidates_list_validator_missing_key() -> None:
    """Surface diagnostics when required keys are absent."""
    result = DiscoveryResult(
        candidates=(_candidate("config.json", {"host": "db"}),),
    )

    validation = validate_candidates(result, validator=["host", "port"])

    candidate = validation.candidates[0]
    assert candidate.data is None
    detail = candidate.diagnostics[-1]
    assert detail.stage == "validation.list"
    assert detail.data["missing_keys"] == ("port",)


def test_validate_candidates_dict_validator_coercion() -> None:
    """Coerce dictionary values according to the validator mapping."""
    result = DiscoveryResult(
        candidates=(_candidate("config.json", {"port": "5432"}),),
    )

    validation = validate_candidates(result, validator={"port": int})

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

    validation = validate_candidates(result, validator=DatabaseConfig)

    success, failure = validation.candidates
    assert isinstance(success.data, DatabaseConfig)
    assert success.data.port == 5432

    assert failure.data is None
    detail = failure.diagnostics[-1]
    assert detail.stage == "validation.dataclass"
    assert "missing required field" in detail.data["errors"][0]
