"""Core orchestration for configuration loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fig_jam.loader._exceptions import ConfigError
from fig_jam.loader._messages import render_error
from fig_jam.pipeline import (
    ConfigBatch,
    ValidationStatus,
    discover,
    override,
    parse,
    validate,
)


def get_config(
    path: os.PathLike[str] | str | None = None,
    section: str | None = None,
    *,
    validator: Any | None = None,
    strict: bool = True,
) -> Any:
    """Load, validate, and return configuration data or raise ConfigError.

    Args:
        path: Optional path to a config file or directory. Defaults to Path.home().
        section: Optional top-level section to extract before validation.
        validator: Optional schema (list[str], dict[str, type], dataclass, or
            Pydantic model) applied during validation.
        strict: Whether to drop extra keys for list validators. Must be True for
            other validator types.

    Returns:
        Validated configuration payload shaped by the provided validator.

    Raises:
        ConfigError: When discovery, parsing, overrides, or validation fail to
            yield exactly one valid configuration source.

    TODO: Change `strict` to `extra_keys` with options 'keep', 'drop', 'error'.
          The `drop` option will be the default, mimicking current behavior.
          The `keep` option will only be available for list validators.
          The `error` option will raise an error on extra keys for any validator type.
    """
    root_path = Path(path) if path is not None else Path.home()
    batch = ConfigBatch(
        root_path=root_path,
        section=section,
        validator=validator,
        strict=bool(strict),
    )
    batch = _run_pipeline(batch)
    validated = [
        source
        for source in batch.sources
        if source.stage_status is ValidationStatus.SUCCESS
    ]
    if len(validated) == 1:
        return validated[0].payload
    message = render_error(batch)
    raise ConfigError(message, batch)


def _run_pipeline(batch: ConfigBatch) -> ConfigBatch:
    """Execute pipeline stages in order, respecting fatal batch errors."""
    if batch.error_code is not None:
        return batch
    return validate(override(parse(discover(batch))))
