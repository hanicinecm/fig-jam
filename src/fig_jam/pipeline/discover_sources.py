"""Discovery stage implementations for fig_jam."""

from __future__ import annotations

from enum import Enum

from fig_jam.parsers import iter_supported_suffixes
from fig_jam.pipeline._model import (
    BatchErrorCode,
    ConfigBatch,
    ConfigSource,
    PipelineStage,
)


class DiscoveryStatus(str, Enum):
    """Status codes emitted by the discovery stage."""

    DISCOVERED = "discovered"
    PATH_NOT_ACCESSIBLE = "path-not-accessible"

    # TODO: When is the PATH_NOT_ACCESSIBLE status used?


def discover(batch: ConfigBatch) -> ConfigBatch:
    """Populate batch sources after inspecting the provided root path."""
    path = batch.root_path
    if path.is_file():
        sources = [ConfigSource(path=path)]
    elif path.is_dir():
        suffixes = tuple(sorted(iter_supported_suffixes()))
        entries_candidates = sorted(path.iterdir(), key=lambda item: item.name)
        sources = [
            ConfigSource(path=entry)
            for entry in entries_candidates
            if entry.is_file() and entry.suffix in suffixes
        ]
    else:
        batch.error_code = BatchErrorCode.NOT_FILE_OR_DIRECTORY
        return batch

    batch.sources = sources
    for source in batch.sources:
        source.last_visited_stage = PipelineStage.DISCOVER
        source.stage_status = DiscoveryStatus.DISCOVERED
        source.stage_error_metadata = {}
    return batch
