"""Discovery stage implementations for fig_jam."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

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


def _build_inaccessible_source(path: Path) -> ConfigSource:
    source = object.__new__(ConfigSource)
    source.path = path
    source.raw_payload = None
    source.payload = None
    source.applied_overrides = {}
    source.last_visited_stage = PipelineStage.DISCOVER
    source.stage_status = DiscoveryStatus.PATH_NOT_ACCESSIBLE
    source.stage_error_metadata = {"message": "permission denied"}
    return source


def discover(batch: ConfigBatch) -> ConfigBatch:
    """Populate batch sources after inspecting the provided root path."""
    if batch.error_code is not None:
        return batch
    path = batch.root_path
    try:
        exists = path.exists()
    except PermissionError:
        batch.error_code = BatchErrorCode.PATH_NOT_ACCESSIBLE
        return batch
    if not exists:
        batch.error_code = BatchErrorCode.PATH_NOT_FOUND
        return batch

    sources: list[ConfigSource] = []
    try:
        is_file = path.is_file()
    except PermissionError:
        batch.error_code = BatchErrorCode.PATH_NOT_ACCESSIBLE
        return batch

    if is_file:
        try:
            sources = [ConfigSource(path=path)]
        except PermissionError:
            batch.error_code = BatchErrorCode.PATH_NOT_ACCESSIBLE
            return batch
    elif path.is_dir():
        try:
            entries_candidates = sorted(path.iterdir(), key=lambda item: item.name)
        except PermissionError:
            batch.error_code = BatchErrorCode.PATH_NOT_ACCESSIBLE
            return batch
        suffixes = tuple(sorted(iter_supported_suffixes()))
        for entry in entries_candidates:
            try:
                if not entry.is_file():
                    continue
            except PermissionError:
                sources.append(_build_inaccessible_source(entry))
                continue
            if entry.suffix not in suffixes:
                continue
            try:
                sources.append(ConfigSource(path=entry))
            except PermissionError:
                sources.append(_build_inaccessible_source(entry))
    else:
        batch.error_code = BatchErrorCode.NOT_FILE_OR_DIRECTORY
        return batch

    batch.sources = sources
    for source in batch.sources:
        if source.stage_status is None:
            source.last_visited_stage = PipelineStage.DISCOVER
            source.stage_status = DiscoveryStatus.DISCOVERED
            source.stage_error_metadata = {}
    return batch
