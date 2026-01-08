"""Public surface for the fig_jam._parsers package.

This module defines the exports that other packages rely on when working with
fig_jam parsers: the parser callable type, the public errors, and the helpers
for discovering registered parsers by suffix.
"""

from fig_jam._parsers.errors import (
    ParserDecodingError as ParserDecodingError,
)
from fig_jam._parsers.errors import (
    ParserDependencyError as ParserDependencyError,
)
from fig_jam._parsers.errors import (
    ParserSyntaxError as ParserSyntaxError,
)
from fig_jam._parsers.errors import (
    ParserTypeError as ParserTypeError,
)
from fig_jam._parsers.registry import (
    Parser as Parser,
)
from fig_jam._parsers.registry import (
    get_parser as get_parser,
)
from fig_jam._parsers.registry import (
    iter_supported_suffixes as iter_supported_suffixes,
)
