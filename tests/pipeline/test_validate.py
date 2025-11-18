"""Tests for the validation pipeline stage."""

import dataclasses
from pathlib import Path

import pytest

from fig_jam.pipeline import (
    ConfigBatch,
    ValidationStatus,
    discover,
    override,
    parse,
    validate,
)


def _run_pipeline(batch: ConfigBatch) -> ConfigBatch:
    discover(batch)
    parse(batch)
    override(batch)
    return batch


def test_validate_no_validator_leaves_payload(tmp_path: Path) -> None:
    """Sources without validators retain their payloads."""
    path = tmp_path / "config.json"
    path.write_text('{"key": "value"}')
    batch = ConfigBatch(root_path=path, section=None, validator=None)

    _run_pipeline(batch)
    validate(batch)

    source = batch.sources[0]
    assert source.stage_status == ValidationStatus.NO_VALIDATOR
    assert source.payload == {"key": "value"}


def test_validate_list_validator_filters_keys(tmp_path: Path) -> None:
    """List validators select only the requested keys."""
    path = tmp_path / "config.json"
    path.write_text('{"keep": 1, "drop": 2}')
    batch = ConfigBatch(root_path=path, section=None, validator=["keep"])

    _run_pipeline(batch)
    validate(batch)

    source = batch.sources[0]
    assert source.stage_status == ValidationStatus.VALIDATED
    assert source.payload == {"keep": 1}


def test_validate_dict_validator_coerces_values(tmp_path: Path) -> None:
    """Dict validators coerce values to the requested types."""
    path = tmp_path / "config.json"
    path.write_text('{"count": "5", "names": ["a", "b"]}')
    batch = ConfigBatch(
        root_path=path, section=None, validator={"count": int, "names": list}
    )

    _run_pipeline(batch)
    validate(batch)

    source = batch.sources[0]
    assert source.stage_status == ValidationStatus.VALIDATED
    assert source.payload == {"count": 5, "names": ["a", "b"]}


def test_validate_dict_validator_missing_key(tmp_path: Path) -> None:
    """Missing keys raise validation errors with metadata."""
    path = tmp_path / "config.json"
    path.write_text('{"count": "5"}')
    batch = ConfigBatch(
        root_path=path, section=None, validator={"count": int, "names": list}
    )

    _run_pipeline(batch)
    validate(batch)

    source = batch.sources[0]
    assert source.stage_status == ValidationStatus.VALIDATION_ERROR
    assert source.stage_error_metadata["missing_key"] == "names"


@dataclasses.dataclass
class Catalog:
    """Catalog model used for dataclass validation tests."""

    title: str


def test_validate_dataclass_instantiation(tmp_path: Path) -> None:
    """Dataclass validators instantiate their target types."""
    path = tmp_path / "config.json"
    path.write_text('{"title": "book"}')
    batch = ConfigBatch(root_path=path, section=None, validator=Catalog)

    _run_pipeline(batch)
    validate(batch)

    source = batch.sources[0]
    assert source.stage_status == ValidationStatus.VALIDATED
    assert isinstance(source.payload, Catalog)


def test_validate_dataclass_errors(tmp_path: Path) -> None:
    """Missing dataclass fields surface validation errors."""
    path = tmp_path / "config.json"
    path.write_text("{}")
    batch = ConfigBatch(root_path=path, section=None, validator=Catalog)

    _run_pipeline(batch)
    validate(batch)

    source = batch.sources[0]
    assert source.stage_status == ValidationStatus.VALIDATION_ERROR
    assert "message" in source.stage_error_metadata


def test_validate_pydantic_model(tmp_path: Path) -> None:
    """Pydantic validators are supported when installed."""
    pydantic = pytest.importorskip("pydantic")

    class Schema(pydantic.BaseModel):
        value: int

    path = tmp_path / "config.json"
    path.write_text('{"value": "10"}')
    batch = ConfigBatch(root_path=path, section=None, validator=Schema)

    _run_pipeline(batch)
    validate(batch)

    source = batch.sources[0]
    assert source.stage_status == ValidationStatus.VALIDATED
    assert source.payload.value == 10  # type: ignore[attr-defined]
