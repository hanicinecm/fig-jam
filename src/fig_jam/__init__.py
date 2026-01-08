"""Public interface for the fig_jam package."""

import importlib.metadata

from fig_jam._loader import ConfigError, load_config

__version__ = importlib.metadata.version(__name__)
__all__ = ["ConfigError", "load_config"]
