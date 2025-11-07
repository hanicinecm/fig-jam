"""Tests for the validation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from fig_jam.exceptions import DiagnosticDetail
from fig_jam.pipeline import PipelineBatch, PipelineCandidate
from fig_jam.validation import validate_candidates


def _batch(*candidates: PipelineCandidate) -> PipelineBatch:
    """Create a pipeline batch for validation tests."""
    if not candidates:
        msg = "At least one candidate must be provided."
        raise ValueError(msg)
    return PipelineBatch(candidates)


def _candidate(path: str, data: dict[str, object] | None) -> PipelineCandidate:
    """Create a pipeline candidate populated with JSON parser diagnostics."""
    diagnostics = (DiagnosticDetail(stage="parsers.json", message="ok"),)
    payload = None if data is None else dict(data)
    return PipelineCandidate(
        source_path=Path(path),
        data=payload,
        diagnostics=diagnostics,
    )


def test_validate_candidates_without_validator() -> None:
    """Return discovery data unchanged when no validator is supplied."""
    batch = _batch(_candidate("config.json", {"feature": "fig"}))

    result = validate_candidates(batch, validator=None)

    candidate = next(iter(result))
    assert candidate.data is not None
    assert dict(candidate.data) == {"feature": "fig"}
    assert candidate.diagnostics[-1].stage == "validation.none"


def test_validate_candidates_list_validator_missing_key() -> None:
    """Surface diagnostics when required keys are absent."""
    batch = _batch(_candidate("config.json", {"host": "db"}))

    result = validate_candidates(batch, validator=["host", "port"])

    candidate = next(iter(result))
    assert candidate.data is None
    detail = candidate.diagnostics[-1]
    assert detail.stage == "validation.list"
    assert detail.data is not None
    assert detail.data["missing_keys"] == ("port",)


def test_validate_candidates_dict_validator_coercion() -> None:
    """Coerce dictionary values according to the validator mapping."""
    batch = _batch(_candidate("config.json", {"port": "5432"}))

    result = validate_candidates(batch, validator={"port": int})

    candidate = next(iter(result))
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

    batch = _batch(
        _candidate("config.json", {"host": "db", "port": "5432"}),
        _candidate("missing.json", {"host": "db"}),
    )

    result = validate_candidates(batch, validator=DatabaseConfig)

    success, failure = tuple(result)
    assert isinstance(success.data, DatabaseConfig)
    assert success.data.port == 5432

    assert failure.data is None
    detail = failure.diagnostics[-1]
    assert detail.stage == "validation.dataclass"
    assert detail.data is not None
    assert "missing required field" in detail.data["errors"][0]


def test_validate_candidates_pydantic_model() -> None:
    """Validate using a Pydantic schema when available."""
    pydantic = pytest.importorskip("pydantic")

    class AppConfig(pydantic.BaseModel):  # type: ignore[attr-defined]
        host: str
        token: str

    batch = _batch(_candidate("config.json", {"host": "api", "token": "secret"}))

    result = validate_candidates(batch, validator=AppConfig)

    candidate = next(iter(result))
    assert isinstance(candidate.data, AppConfig)
    assert candidate.data.host == "api"
