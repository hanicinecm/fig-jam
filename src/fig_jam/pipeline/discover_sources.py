"""Discovery stage implementation."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from fig_jam.parsers import iter_supported_suffixes
from fig_jam.pipeline._model import (
    ConfigBatch,
    ConfigSource,
    PipelineStage,
)


class DiscoveryStatus(str, Enum):
    """Status codes emitted by the discovery stage."""

    SUCCESS = "success"
    PATH_NOT_FOUND_ERROR = "path-not-found-error"


def discover(batch: ConfigBatch) -> ConfigBatch:
    """Populate batch sources after inspecting the provided root path.

    If the root path has a suffix (i.e., it's a file path), a single source is
    created for it. If the file doesn't exist, the source is marked with
    PATH_NOT_FOUND status.

    If the root path has no suffix (i.e., it's a directory), the directory is
    scanned for files with supported config formats. If the directory doesn't
    exist or contains no valid config files, the sources list stays empty.
    """
    if batch.error_code is not None:
        return batch

    root_path = batch.root_path
    suffix = root_path.suffix.lower()

    # Collect candidate paths
    paths: list[Path] = []
    if suffix:
        # Root path is a file - include it even if it doesn't exist
        paths.append(root_path)
    elif root_path.is_dir():
        # Root path is a directory - collect existing config files
        supported = set(iter_supported_suffixes())
        paths.extend(
            child
            for child in root_path.iterdir()
            if child.is_file() and child.suffix.lower() in supported
        )

    # Create sources from collected paths
    for path in paths:
        source = ConfigSource(path=path)
        source.last_visited_stage = PipelineStage.DISCOVER
        source.stage_error_metadata = {}
        if path.exists():
            source.stage_status = DiscoveryStatus.SUCCESS
        else:
            source.stage_status = DiscoveryStatus.PATH_NOT_FOUND_ERROR
        batch.sources.append(source)

    return batch
