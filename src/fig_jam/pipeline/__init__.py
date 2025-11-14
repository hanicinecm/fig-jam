"""Public surface for the configuration processing pipeline.

This sub-package exposes the shared candidate containers and re-exports the
individual pipeline stages so callers can opt into each step explicitly.
"""

from fig_jam.pipeline._pipeline_utils import PipelineBatch, PipelineCandidate
from fig_jam.pipeline.discovery import discover_candidates
from fig_jam.pipeline.overrides import override_candidates
from fig_jam.pipeline.validation import validate_candidates

__all__ = [
    "PipelineBatch",
    "PipelineCandidate",
    "discover_candidates",
    "override_candidates",
    "validate_candidates",
]
