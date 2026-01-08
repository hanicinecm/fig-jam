"""Public interface for the fig_jam package."""

import importlib.metadata

from fig_jam._loader._core import load_config
from fig_jam._loader._exceptions import ConfigError

__version__ = importlib.metadata.version(__name__)
__all__ = ["ConfigError", "load_config"]
