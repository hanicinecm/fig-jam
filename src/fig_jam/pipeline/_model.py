"""Data models shared across the `fig_jam.pipeline` stages.

Each model captures the minimal state and diagnostics required by the
discovery, parsing, override, and validation stages as they examine candidate
config files.

TODO: Figure how to deal with no valid sources in the case of a model validator with
    fully optional fields. An empty fallback source, which would pass through
    override and validation (only if no standard sources make it through)?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fig_jam.parsers import iter_supported_suffixes
from fig_jam.pipeline._validators import (
    collect_env_override_paths,
    is_supported_validator,
)


class BatchErrorCode(str, Enum):
    """Fatal failure codes that short-circuit the pipeline.

    These errors represent problems that prevent any config file from entering
    the normal stage flow: missing paths, inaccessible locations, invalid
    targets, or unsupported validator types supplied up front.
    """

    INVALID_PATH = "invalid-path"
    INVALID_VALIDATOR_TYPE = "invalid-validator-type"
    INVALID_ENV_OVERRIDE = "invalid-env-override"


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
    `validator`.

    The root path existence and type (file vs. directory) is not checked here,
    but rather in the discovery stage.
    However, its suffix needs to either be empty (for directories) or match a
    recognized config format (for files), otherwise an error code is set.

    The `validator` is parsed for the environment override paths here.
    As an example, if the validator is a dataclass with an attribute `database`, which
    in turn is another dataclass with defined __env_overrides__ for its field `host`,
    the `env_overrides` mapping will contain an entry mapping the path
    `("database", "host")` to the corresponding environment variable name.
    Validity of the override paths is also checked here, and an error code is set
    if any paths are invalid.
    """

    root_path: Path
    section: str | None
    validator: Any | None
    env_overrides: dict[tuple[str, ...], str] = field(default_factory=dict)
    sources: list[ConfigSource] = field(default_factory=list)
    error_code: BatchErrorCode | None = None

    def __post_init__(self) -> None:
        # Check that the root path is valid:
        suffix = self.root_path.suffix.lower()
        if suffix and suffix not in iter_supported_suffixes():
            self.error_code = BatchErrorCode.INVALID_PATH
            return
        # Check that the validator is of a supported type.
        if self.validator is not None and not is_supported_validator(self.validator):
            self.error_code = BatchErrorCode.INVALID_VALIDATOR_TYPE
            return
        # Collect environment override paths from the validator.
        try:
            self.env_overrides = collect_env_override_paths(self.validator)
        except AttributeError:
            self.error_code = BatchErrorCode.INVALID_ENV_OVERRIDE
            return
