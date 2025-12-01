"""Exception types raised by the loader."""

from __future__ import annotations

from fig_jam.pipeline import ConfigBatch


class ConfigError(Exception):
    """Raised when configuration loading fails."""

    def __init__(self, message: str, batch: ConfigBatch) -> None:
        super().__init__(message)
        self.batch = batch
