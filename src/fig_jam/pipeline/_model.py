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
    is_list_validator,
    is_supported_validator,
)


class BatchErrorCode(str, Enum):
    """Fatal failure codes that short-circuit the pipeline.

    These errors represent problems that prevent any config file from entering
    the normal stage flow: invalid targets, or unsupported validator
    targets, or unsupported validator types supplied up front.
    """

    UNSUPPORTED_FORMAT = "unsupported-format"
    DIRECTORY_ACCESS_ERROR = "directory-access-error"
    INVALID_VALIDATOR_TYPE = "invalid-validator-type"
    INVALID_ENV_OVERRIDE = "invalid-env-override"
    INVALID_STRICT_VALUE = "invalid-strict-value"


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

    Each configuration source corresponds to a *single file path* which may or
    may not exist on disk. Sources are instantiated in the discovery stage.

    As the instance progresses through the pipeline, it tracks the file `path`,
    the immutable `raw_payload` produced by parsing (after section extraction),
    and the mutable `payload` that is transformed by overrides and validation.
    Diagnostics such as the last visited `PipelineStage`, the emitted status,
    error metadata, and any `applied_overrides` live on this object so the
    loader can explain why a candidate succeeded or failed.
    """

    path: Path
    raw_payload: MappingProxyType[str, Any] | None = None
    payload: Any | None = None
    applied_overrides: dict[str, str] = field(default_factory=dict)
    last_visited_stage: PipelineStage | None = None
    stage_status: str | None = None
    stage_error_metadata: dict[str, Any] = field(default_factory=dict)


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
    strict: bool = True
    env_overrides: dict[tuple[str, ...], str] = field(default_factory=dict)
    sources: list[ConfigSource] = field(default_factory=list)
    error_code: BatchErrorCode | None = None

    def __post_init__(self) -> None:
        # Check that the root path has a valid suffix:
        suffix = self.root_path.suffix.lower()
        if suffix and suffix not in iter_supported_suffixes():
            self.error_code = BatchErrorCode.UNSUPPORTED_FORMAT
            return
        # Check that directory root paths are accessible:
        if not suffix and self.root_path.is_dir():
            try:
                next(self.root_path.iterdir(), None)
            except PermissionError:
                self.error_code = BatchErrorCode.DIRECTORY_ACCESS_ERROR
                return
        # Check that the validator is of a supported type.
        if self.validator is not None and not is_supported_validator(self.validator):
            self.error_code = BatchErrorCode.INVALID_VALIDATOR_TYPE
            return
        # Check that strict=False is only used with list validators or no validator.
        if (
            not self.strict
            and self.validator is not None
            and not is_list_validator(self.validator)
        ):
            self.error_code = BatchErrorCode.INVALID_STRICT_VALUE
            return
        # Collect environment override paths from the validator.
        try:
            self.env_overrides = collect_env_override_paths(self.validator)
        except AttributeError:
            self.error_code = BatchErrorCode.INVALID_ENV_OVERRIDE
            return
