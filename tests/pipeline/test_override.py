"""Tests for the override pipeline stage."""

import dataclasses
from pathlib import Path
from typing import ClassVar

import pytest

from fig_jam.pipeline import (
    ConfigBatch,
    OverridesStatus,
    PipelineStage,
    discover,
    override,
    parse,
)


@dataclasses.dataclass
class Credentials:
    """Credentials payload used by the override tests."""

    value: str
    __env_overrides__: ClassVar[dict[str, str]] = {"value": "APP_VALUE"}


@dataclasses.dataclass
class DatabaseConfig:
    """Top-level database model used in override scenarios."""

    credentials: Credentials


def _prepare_batch(tmp_path: Path) -> tuple[ConfigBatch, Path]:
    path = tmp_path / "config.json"
    batch = ConfigBatch(root_path=path, section=None, validator=DatabaseConfig)
    return batch, path


def test_override_applies_env_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Overrides replace the payload values when environment variables exist."""
    batch, path = _prepare_batch(tmp_path)
    path.write_text('{"credentials": {"value": "initial"}}')
    monkeypatch.setenv("APP_VALUE", "replacement")

    discover(batch)
    parse(batch)
    override(batch)

    source = batch.sources[0]
    assert source.stage_status == OverridesStatus.CONFIGURED
    assert source.payload is not None
    assert source.payload["credentials"]["value"] == "replacement"
    assert source.applied_overrides == {"credentials.value": "APP_VALUE"}
    assert source.last_visited_stage == PipelineStage.OVERRIDE


def test_override_reports_missing_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing override targets lead to a field-error status."""
    batch, path = _prepare_batch(tmp_path)
    path.write_text('{"credentials": {}}')
    monkeypatch.setenv("APP_VALUE", "replacement")

    discover(batch)
    parse(batch)
    override(batch)

    source = batch.sources[0]
    assert source.stage_status == OverridesStatus.FIELD_ERROR
    assert source.stage_error_metadata["path"] == "credentials.value"
    assert source.applied_overrides == {}


def test_override_not_configured_without_model(tmp_path: Path) -> None:
    """Overrides stage marks sources as not configured when no dataclass is used."""
    path = tmp_path / "config.json"
    path.write_text('{"key": "value"}')
    batch = ConfigBatch(root_path=path, section=None, validator=["key"])

    discover(batch)
    parse(batch)
    override(batch)

    source = batch.sources[0]
    assert source.stage_status == OverridesStatus.NOT_CONFIGURED
    assert source.applied_overrides == {}
