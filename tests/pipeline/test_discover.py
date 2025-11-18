"""Tests for the discovery pipeline stage."""

from pathlib import Path

from fig_jam.pipeline import BatchErrorCode, ConfigBatch, DiscoveryStatus, discover


def test_discover_reports_missing_path(tmp_path: Path) -> None:
    """Missing paths signal the appropriate batch error code."""
    batch = ConfigBatch(
        root_path=tmp_path / "missing", section=None, validator=None
    )
    discover(batch)
    assert batch.error_code is BatchErrorCode.PATH_NOT_FOUND
    assert batch.sources == []


def test_discover_enumerates_supported_configs(tmp_path: Path) -> None:
    """Supported files are discovered deterministically."""
    root = tmp_path / "configs"
    root.mkdir()
    (root / "b.json").write_text("{}")
    (root / "a.toml").write_text("key = 'value'")
    (root / "z.ini").write_text("[section]\nkey=value")
    (root / "ignore.txt").write_text("skip")

    batch = ConfigBatch(root_path=root, section=None, validator=None)
    discover(batch)

    names = [source.path.name for source in batch.sources]
    assert names == ["a.toml", "b.json", "z.ini"]
    assert all(
        source.stage_status == DiscoveryStatus.DISCOVERED for source in batch.sources
    )


def test_discover_returns_empty_when_no_supported_files(tmp_path: Path) -> None:
    """Directories without supported extensions yield an empty batch."""
    root = tmp_path / "configs"
    root.mkdir()
    (root / "notes.txt").write_text("meta")

    batch = ConfigBatch(root_path=root, section=None, validator=None)
    discover(batch)
    assert batch.error_code is None
    assert batch.sources == []
