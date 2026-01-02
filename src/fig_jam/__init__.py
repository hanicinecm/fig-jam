"""Public interface for the fig_jam package."""

import importlib.metadata

from fig_jam.loader import ConfigError, get_config

__version__ = importlib.metadata.version(__name__)
__all__ = ["ConfigError", "get_config"]
