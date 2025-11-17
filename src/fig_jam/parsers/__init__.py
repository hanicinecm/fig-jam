"""Public surface for the fig_jam.parsers package.

This module defines the exports that other packages rely on when working with
fig_jam parsers: the parser callable type, the public errors, and the helpers
for discovering registered parsers by suffix.
"""

from fig_jam.parsers._parsers import Parser, get_parser, iter_supported_suffixes
from fig_jam.parsers._parsers_errors import (
    ParserDecodingError,
    ParserDependencyError,
    ParserSyntaxError,
    ParserTypeError,
)

__all__ = [
    "Parser",
    "ParserDecodingError",
    "ParserDependencyError",
    "ParserSyntaxError",
    "ParserTypeError",
    "get_parser",
    "iter_supported_suffixes",
]
