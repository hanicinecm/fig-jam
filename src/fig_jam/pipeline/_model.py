"""Data models shared across the `fig_jam.pipeline` stages.

Each model captures the minimal state and diagnostics required by the
discovery, parsing, override, and validation stages as they examine candidate
config files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fig_jam.pipeline._validators import is_supported_validator


class BatchErrorCode(str, Enum):
    """Fatal failure codes that short-circuit the pipeline.

    These errors represent problems that prevent any config file from entering
    the normal stage flow: missing paths, inaccessible locations, invalid
    targets, or unsupported validator types supplied up front.
    """

    PATH_NOT_FOUND = "path-not-found"
    PATH_NOT_ACCESSIBLE = "path-not-accessible"
    NOT_FILE_OR_DIRECTORY = "not-file-or-directory"
    INVALID_VALIDATOR_TYPE = "invalid-validator-type"


class PipelineStage(str, Enum):
    """Labels that record which pipeline stage last touched a source.

    Sources transition through the `DISCOVER`, `PARSE`, `OVERRIDE`, and
    `VALIDATE` stages, and the progress is recorded in the `ConfigSource` instances
    via this enum to control flow and diagnostics.
    """

    DISCOVER = "discover"
    PARSE = "parse"
    OVERRIDE = "override"
    VALIDATE = "validate"


@dataclass
class ConfigSource:
    """Metadata for a single configuration candidate inside the pipeline.

    Each configuration source corresponds to a *single existing file* on disk.
    The sources are instantiated in the discovery stage when files are found.

    As the instance progresses through the pipeline, a it tracks the file `path`, the
    immutable `raw_payload` produced by parsing (after section extraction), and the
    mutable `payload` that is transformed by overrides and validation.
    Diagnostics such as the last visited `PipelineStage`, the emitted status,
    error metadata, and any `applied_overrides` live on this object so the loader can
    explain why a candidate succeeded or failed.
    """

    path: Path
    raw_payload: MappingProxyType[str, Any] | None = None
    payload: Any | None = None
    applied_overrides: dict[str, str] = field(default_factory=dict)
    last_visited_stage: PipelineStage | None = None
    stage_status: str | None = None
    stage_error_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.path.exists():
            message = f"config source path does not exist: {self.path!r}"
            raise ValueError(message)


@dataclass
class ConfigBatch:
    """Wrapper that threads ConfigSource instances through the pipeline stages.

    The batch records the user-supplied `root_path`, optional `section`, and
    `validator`, the list of *all* (active and rejected) `sources`, and an
    optional terminal `error_code` when discovery cannot produce any candidates
    at all.

    The root path may point to a file or directory. If the root path does not exist,
    or is not accessible, or is neither a file nor directory, the appropriate
    `error_code` is set right away.
    Similarly, if the supplied validator is of an unsupported type, the
    `error_code` is set to reflect that.
    """

    root_path: Path
    section: str | None
    validator: Any | None
    sources: list[ConfigSource] = field(default_factory=list)
    error_code: BatchErrorCode | None = None

    def __post_init__(self) -> None:
        # Check that the root path exists and is accessible.
        try:
            if not self.root_path.exists():
                self.error_code = BatchErrorCode.PATH_NOT_FOUND
                return
        except PermissionError:
            self.error_code = BatchErrorCode.PATH_NOT_ACCESSIBLE
            return

        # Check that the validator is of a supported type.
        if self.validator is not None and not is_supported_validator(self.validator):
            self.error_code = BatchErrorCode.INVALID_VALIDATOR_TYPE
