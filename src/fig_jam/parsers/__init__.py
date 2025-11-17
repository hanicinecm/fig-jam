"""Public surface for fig_jam.parsers package."""

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
