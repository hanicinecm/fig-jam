"""Tests for the parsing pipeline stage."""

from pathlib import Path

from fig_jam.pipeline import ConfigBatch, ParsingStatus, discover, parse


def _prepare_batch(
    tmp_path: Path, section: str | None = None
) -> tuple[ConfigBatch, Path]:
    path = tmp_path / "config.json"
    batch = ConfigBatch(root_path=path, section=section, validator=None)
    return batch, path


def test_parse_extracts_sections(tmp_path: Path) -> None:
    """Parse stage should extract the requested section when present."""
    batch, path = _prepare_batch(tmp_path, section="database")
    path.write_text('{"database": {"host": "example"}, "other": 1}')

    discover(batch)
    parse(batch)

    source = batch.sources[0]
    assert source.stage_status == ParsingStatus.PARSED
    assert source.payload == {"host": "example"}
    assert source.raw_payload is not None
    assert source.raw_payload["database"]["host"] == "example"


def test_parse_records_missing_section(tmp_path: Path) -> None:
    """Missing sections surface the missing-section status."""
    batch, path = _prepare_batch(tmp_path, section="missing")
    path.write_text('{"one": 1}')

    discover(batch)
    parse(batch)

    source = batch.sources[0]
    assert source.stage_status == ParsingStatus.MISSING_SECTION_ERROR
    assert source.stage_error_metadata["section"] == "missing"
    assert "one" in source.stage_error_metadata["available_keys"]
    assert source.payload is None


def test_parse_non_mapping_payload(tmp_path: Path) -> None:
    """Parser type errors keep the metadata about the actual type."""
    batch, path = _prepare_batch(tmp_path)
    path.write_text("[1, 2, 3]")

    discover(batch)
    parse(batch)

    source = batch.sources[0]
    assert source.stage_status == ParsingStatus.TYPE_ERROR
    assert source.stage_error_metadata["actual"] == "list"
