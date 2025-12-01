"""Human-readable error message rendering for the loader."""

from __future__ import annotations

from collections.abc import Callable

from fig_jam.parsers import iter_supported_suffixes
from fig_jam.pipeline import (
    BatchErrorCode,
    ConfigBatch,
    ConfigSource,
    DiscoveryStatus,
    OverridesStatus,
    ParsingStatus,
    PipelineStage,
    ValidationStatus,
)

StageRenderer = Callable[[ConfigSource], str]
StageKey = tuple[PipelineStage, str]


def render_error(batch: ConfigBatch) -> str:
    """Compose a user-facing message from a populated ConfigBatch."""
    if batch.error_code is not None:
        return _render_batch_error(batch)

    if not batch.sources:
        return _render_no_sources(batch)

    validated = _validated_sources(batch)
    if len(validated) > 1:
        return _render_multiple_validated(batch, validated)

    failed = [source for source in batch.sources if source not in validated]
    if len(batch.sources) == 1:
        return _render_single_failure(batch.sources[0])

    if not validated and failed:
        return _render_all_failed(batch, failed)

    return (
        "Configuration loading failed for an unknown reason; no diagnostics "
        "were recorded."
    )


def _render_batch_error(batch: ConfigBatch) -> str:
    renderers: dict[BatchErrorCode, Callable[[ConfigBatch], str]] = {
        BatchErrorCode.UNSUPPORTED_FORMAT: _render_unsupported_format,
        BatchErrorCode.DIRECTORY_ACCESS_ERROR: _render_directory_access_error,
        BatchErrorCode.INVALID_VALIDATOR_TYPE: _render_invalid_validator_type,
        BatchErrorCode.INVALID_ENV_OVERRIDE: _render_invalid_env_override,
        BatchErrorCode.INVALID_STRICT_VALUE: _render_invalid_strict_value,
    }
    renderer = renderers.get(batch.error_code)
    if renderer is None:
        return "Configuration loading failed: unknown batch error."
    return renderer(batch)


def _render_unsupported_format(batch: ConfigBatch) -> str:
    supported = ", ".join(iter_supported_suffixes())
    return (
        f"Unsupported config format for path '{batch.root_path}'. Supported "
        f"extensions: {supported}. Use a supported file or point to a directory."
    )


def _render_directory_access_error(batch: ConfigBatch) -> str:
    return (
        f"Cannot access directory '{batch.root_path}'. Adjust permissions or "
        "choose a different path."
    )


def _render_invalid_validator_type(batch: ConfigBatch) -> str:
    validator_type = type(batch.validator).__name__
    return (
        f"Validator of type '{validator_type}' is not supported. Use list[str], "
        "dict[str, type], a dataclass, a Pydantic model, or None."
    )


def _render_invalid_env_override(batch: ConfigBatch) -> str:
    validator_type = type(batch.validator).__name__
    return (
        f"Invalid __env_overrides__ declared on validator '{validator_type}'. "
        "Ensure overrides reference existing fields."
    )


def _render_invalid_strict_value(batch: ConfigBatch) -> str:
    return (
        f"strict={batch.strict} is only allowed with a list[str] validator or no "
        "validator. Use strict=True or change the validator type."
    )


def _render_no_sources(batch: ConfigBatch) -> str:
    supported = ", ".join(iter_supported_suffixes())
    return (
        f"No configuration files found under '{batch.root_path}' matching "
        f"extensions: {supported}. Create a config file or provide an explicit "
        "path."
    )


def _render_multiple_validated(batch: ConfigBatch, sources: list[ConfigSource]) -> str:
    paths = ", ".join(str(source.path) for source in sources)
    return (
        f"Multiple configuration files matched for '{batch.root_path}' and passed "
        f"validation: {paths}. Provide an explicit path or a narrower validator "
        "to disambiguate."
    )


def _render_single_failure(source: ConfigSource) -> str:
    detail = _render_source_failure(source)
    return f"Configuration loading failed for '{source.path}': {detail}"


def _render_all_failed(batch: ConfigBatch, sources: list[ConfigSource]) -> str:
    header = (
        f"No configuration candidates under '{batch.root_path}' passed "
        "validation or parsing. Failures:"
    )
    details = [
        f"- {source.path}: {_render_source_failure(source)}" for source in sources
    ]
    return "\n".join([header, *details])


def _render_source_failure(source: ConfigSource) -> str:
    key: StageKey | None = None
    if source.last_visited_stage is not None and source.stage_status is not None:
        key = (source.last_visited_stage, source.stage_status.value)
    renderer = _STAGE_STATUS_RENDERERS.get(key, _render_unknown_stage_failure)
    detail = renderer(source)
    if source.last_visited_stage is PipelineStage.VALIDATE and source.applied_overrides:
        detail = f"{detail} {_format_applied_overrides(source.applied_overrides)}"
    return detail


def _render_unknown_stage_failure(source: ConfigSource) -> str:
    if source.last_visited_stage is None:
        return "candidate did not enter the pipeline."
    status = source.stage_status or "unknown status"
    return f"{source.last_visited_stage.value} stage failed with status '{status}'."


def _render_discovery_path_not_found(source: ConfigSource) -> str:
    return (
        f"path '{source.path}' does not exist. Create the file or point to an "
        "existing path with a supported extension."
    )


def _render_file_access_error(source: ConfigSource) -> str:
    message = source.stage_error_metadata.get("message", "unknown error")
    return f"file could not be read: {message}. Check permissions and path."


def _render_missing_dependency(source: ConfigSource) -> str:
    dependency = source.stage_error_metadata.get("dependency", "required library")
    hint = source.stage_error_metadata.get("hint")
    install = f"Install with `uv add {dependency}` or `pip install {dependency}`."
    if hint:
        return (
            f"missing dependency '{dependency}' to parse {source.path.suffix}. "
            f"{install} Hint: {hint}"
        )
    return f"missing dependency '{dependency}' to parse {source.path.suffix}. {install}"


def _render_decoding_error(source: ConfigSource) -> str:
    encodings = source.stage_error_metadata.get("attempted_encodings", [])
    reason = source.stage_error_metadata.get("reason", "decoding failed")
    enc_list = ", ".join(encodings) if encodings else "default encodings"
    return f"failed to decode file (tried {enc_list}): {reason}"


def _render_syntax_error(source: ConfigSource) -> str:
    message = source.stage_error_metadata.get("message", "syntax error")
    return f"could not parse file contents: {message}"


def _render_not_mapping(source: ConfigSource) -> str:
    actual = source.stage_error_metadata.get("actual", "unknown")
    return f"parsed content is not a mapping (got {actual}). Config must be a mapping."


def _render_missing_section(source: ConfigSource) -> str:
    section = source.stage_error_metadata.get("section", "requested section")
    available = source.stage_error_metadata.get("available_keys", [])
    available_list = ", ".join(str(key) for key in available) or "none"
    return f"section '{section}' not found. Available top-level keys: {available_list}."


def _render_missing_keys(source: ConfigSource) -> str:
    missing = source.stage_error_metadata.get("missing_keys", [])
    missing_list = ", ".join(str(key) for key in missing) or "none"
    return (
        f"missing required keys: {missing_list}. Add the missing keys to the "
        "config section."
    )


def _render_coercion_error(source: ConfigSource) -> str:
    errors: dict[str, Exception] = source.stage_error_metadata.get(
        "coercion_errors", {}
    )
    parts = [f"{key} -> {error}" for key, error in sorted(errors.items())]
    joined = "; ".join(parts) if parts else "unknown coercion error"
    return f"failed to coerce values to expected types ({joined})."


def _render_dataclass_instantiation_error(source: ConfigSource) -> str:
    message = source.stage_error_metadata.get("message", "dataclass instantiation")
    return (
        f"dataclass instantiation failed: {message}. Ensure required fields are "
        "provided with correct types."
    )


def _render_pydantic_validation_error(source: ConfigSource) -> str:
    message = source.stage_error_metadata.get("message", "validation failed")
    return f"pydantic validation failed: {message}"


def _format_applied_overrides(overrides: dict[str, str]) -> str:
    pairs = ", ".join(f"{path} <- {env}" for path, env in sorted(overrides.items()))
    return f"Applied environment overrides: {pairs}."


def _validated_sources(batch: ConfigBatch) -> list[ConfigSource]:
    return [
        source
        for source in batch.sources
        if source.stage_status is ValidationStatus.SUCCESS
    ]


_STAGE_STATUS_RENDERERS: dict[StageKey, StageRenderer] = {
    (PipelineStage.DISCOVER, DiscoveryStatus.PATH_NOT_FOUND_ERROR.value): (
        _render_discovery_path_not_found
    ),
    (PipelineStage.PARSE, ParsingStatus.FILE_ACCESS_ERROR.value): (
        _render_file_access_error
    ),
    (PipelineStage.PARSE, ParsingStatus.MISSING_DEPENDENCY_ERROR.value): (
        _render_missing_dependency
    ),
    (PipelineStage.PARSE, ParsingStatus.DECODING_ERROR.value): (_render_decoding_error),
    (PipelineStage.PARSE, ParsingStatus.SYNTAX_ERROR.value): _render_syntax_error,
    (PipelineStage.PARSE, ParsingStatus.NOT_MAPPING_ERROR.value): _render_not_mapping,
    (PipelineStage.PARSE, ParsingStatus.MISSING_SECTION_ERROR.value): (
        _render_missing_section
    ),
    (PipelineStage.VALIDATE, ValidationStatus.MISSING_KEYS_ERROR.value): (
        _render_missing_keys
    ),
    (PipelineStage.VALIDATE, ValidationStatus.TYPE_COERCION_ERROR.value): (
        _render_coercion_error
    ),
    (PipelineStage.VALIDATE, ValidationStatus.DATACLASS_INSTANTIATION_ERROR.value): (
        _render_dataclass_instantiation_error
    ),
    (PipelineStage.VALIDATE, ValidationStatus.PYDANTIC_VALIDATION_ERROR.value): (
        _render_pydantic_validation_error
    ),
    # Override currently emits only SUCCESS; mapping kept for completeness.
    (PipelineStage.OVERRIDE, OverridesStatus.SUCCESS.value): (
        lambda _: "environment overrides applied"
    ),
}
