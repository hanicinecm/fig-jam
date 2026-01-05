"""Parsing stage implementations for fig_jam."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fig_jam.parsers import get_parser
from fig_jam.parsers._parsers_errors import (
    ParserDecodingError,
    ParserDependencyError,
    ParserSyntaxError,
    ParserTypeError,
)
from fig_jam.pipeline._model import ConfigBatch, ConfigSource, PipelineStage
from fig_jam.pipeline.discover_sources import DiscoveryStatus


class ParsingStatus(str, Enum):
    """Status codes emitted by the parsing stage."""

    SUCCESS = "success"
    FILE_ACCESS_ERROR = "file-access-error"
    MISSING_DEPENDENCY_ERROR = "missing-dependency-error"
    DECODING_ERROR = "decoding-error"
    SYNTAX_ERROR = "syntax-error"
    NOT_MAPPING_ERROR = "not-mapping-error"
    MISSING_SECTION_ERROR = "missing-section-error"


def _try_parse_file(source: ConfigSource, path: Path) -> dict[str, Any] | None:
    """Attempt to parse a file, recording errors on the source if any occur.

    Returns:
        The parsed mapping if successful, or None if an error was recorded.
    """
    parser = get_parser(path.suffix)
    try:
        return parser(path)
    except OSError as error:
        source.stage_status = ParsingStatus.FILE_ACCESS_ERROR
        source.stage_error_metadata = {"message": str(error), "exception": error}
    except ParserDependencyError as error:
        source.stage_status = ParsingStatus.MISSING_DEPENDENCY_ERROR
        source.stage_error_metadata = {
            "dependency": error.dependency,
            "hint": getattr(error, "hint", str(error)),
        }
    except ParserDecodingError as error:
        source.stage_status = ParsingStatus.DECODING_ERROR
        source.stage_error_metadata = {
            "attempted_encodings": list(error.attempted_encodings),
            "reason": str(error),
        }
    except ParserSyntaxError as error:
        source.stage_status = ParsingStatus.SYNTAX_ERROR
        source.stage_error_metadata = {
            "message": str(error.error),
            "exception": error.error,
        }
    except ParserTypeError as error:
        source.stage_status = ParsingStatus.NOT_MAPPING_ERROR
        source.stage_error_metadata = {
            "expected": "mapping",
            "actual": error.actual_type.__name__,
        }
    return None


def parse(batch: ConfigBatch) -> ConfigBatch:
    """Parse the configuration files identified by discovery."""
    if batch.error_code is not None:
        return batch
    for source in batch.sources:
        if source.stage_status is not DiscoveryStatus.SUCCESS:
            continue
        source.last_visited_stage = PipelineStage.PARSE
        parsed = _try_parse_file(source, source.path)
        if parsed is None:
            continue
        payload: Any = parsed
        if batch.section is not None:
            if not isinstance(parsed, Mapping) or batch.section not in parsed:
                source.stage_status = ParsingStatus.MISSING_SECTION_ERROR
                available = list(parsed.keys()) if isinstance(parsed, Mapping) else []
                source.stage_error_metadata = {
                    "section": batch.section,
                    "available_keys": available,
                }
                continue
            payload = parsed[batch.section]
        source.raw_payload = MappingProxyType(parsed)
        if isinstance(payload, Mapping):
            source.payload = dict(payload)
        else:
            source.payload = payload
        source.stage_status = ParsingStatus.SUCCESS
        source.stage_error_metadata = {}
    return batch
