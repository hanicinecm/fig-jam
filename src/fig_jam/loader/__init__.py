"""Loader package exposing the public API."""

from fig_jam.loader._core import get_config
from fig_jam.loader._exceptions import ConfigError

__all__ = ["ConfigError", "get_config"]
