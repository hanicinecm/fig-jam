# Task List for Confignostic get_config Implementation

## Relevant Files

- `src/fig_jam/__init__.py` - Publish the public API (`get_config`, `clear_cache`, exceptions).
- `src/fig_jam/exceptions.py` - Define domain exceptions with remediation-focused messaging.
- `src/fig_jam/parsers.py` - House parser registry, format-specific parsers, and encoding handling.
- `src/fig_jam/discovery.py` - Implement candidate enumeration, parsing orchestration, and section extraction.
- `src/fig_jam/overrides.py` - Apply environment-variable overrides prior to validation.
- `src/fig_jam/validation.py` - Validate parsed data against supported schema types.
- `src/fig_jam/cache.py` - Manage memoization, cache key computation, and `clear_cache`.
- `src/fig_jam/loader.py` - Orchestrate the end-to-end load pipeline with logging and diagnostics.
- `tests/` - Mirror module structure with unit and integration coverage for the pipeline.
- `pyproject.toml` - Declare optional dependencies/extras and tooling configuration.
- `README.md` - Document quick-start usage, validators, and override examples.
- `.github/workflows/` - Host CI/CD automation definitions for linting, testing, and release.

## Tasks

- [ ] 1 Establish module scaffolding and exported API surface.
  - [ ] 1.1 Create module files with docstrings, type-hinted signatures, and placeholder implementations aligned with the architecture.
  - [ ] 1.2 Implement domain exceptions structure and share remediation metadata across modules.
  - [ ] 1.3 Update `src/fig_jam/__init__.py` to expose the public API and ensure import side effects (like parser registration) occur on package load.
- [ ] 2 Build parser registry with multi-encoding support and dependency gating.
  - [ ] 2.1 Implement a `register_parser` decorator and central registry keyed by file suffix.
  - [ ] 2.2 Implement JSON, TOML, INI/CFG, and YAML parsers with encoding fallbacks and optional dependency checks.
  - [ ] 2.3 Emit structured parser results and dependency guidance for discovery and diagnostics layers.
- [ ] 3 Implement discovery pipeline for candidate enumeration and section extraction.
  - [ ] 3.1 Normalize input paths (file, directory, or defaults) and enumerate candidates with registered suffixes.
  - [ ] 3.2 Invoke registered parsers, capturing successful data or error payloads without losing context.
  - [ ] 3.3 Extract requested sections and annotate missing-section failures while preserving parsed data immutability guarantees.
- [ ] 4 Implement environment override merging aligned with FIG_JAM naming.
  - [ ] 4.1 Parse environment variable keys into section-aware paths with case-insensitive handling.
  - [ ] 4.2 Merge overrides into immutable mappings prior to validation while surfacing unsupported override attempts.
- [ ] 5 Deliver validator engine covering list, dict, dataclass, and Pydantic schemas.
  - [ ] 5.1 Build validator dispatch plumbing that inspects the supplied schema type and routes accordingly.
  - [ ] 5.2 Implement list/dict validators that perform key filtering, presence checks, and type coercion.
  - [ ] 5.3 Integrate dataclass and Pydantic validation (with optional dependency loading) and normalize validation failures into diagnostic records.
- [ ] 6 Provide caching layer and `clear_cache()` API with thread-safe data handling.
  - [ ] 6.1 Define cache keys that include canonical path, section, validator identity, and override state.
  - [ ] 6.2 Wrap load execution with caching, returning copies where needed to avoid shared mutable state.
  - [ ] 6.3 Expose `clear_cache()` and ensure validator types that cannot be hashed bypass caching gracefully.
- [ ] 7 Compose `get_config` loader workflow with diagnostics, logging, and error shaping.
  - [ ] 7.1 Orchestrate discovery, overrides, validation, and caching to return a single validated candidate.
  - [ ] 7.2 Raise `ConfigSourceNotFoundError` or `ConfigSourceAmbiguityError` with aggregated diagnostics when invariants fail.
  - [ ] 7.3 Emit debug-level logging for discovery attempts, parser selection, and validator outcomes.
- [ ] 8 Update packaging metadata and documentation to reflect new capabilities.
  - [ ] 8.1 Declare optional dependency extras and tooling configuration updates in `pyproject.toml`.
  - [ ] 8.2 Document API usage, validator patterns, overrides, and caching guidance in `README.md`.
  - [ ] 8.3 Align project metadata (e.g., classifiers, versioning notes) with the new feature set.
- [ ] 9 Configure CI/CD automation for linting, testing, coverage, and release publishing.
  - [ ] 9.1 Add GitHub Actions workflows covering linting, formatting, and test matrix execution.
  - [ ] 9.2 Integrate coverage enforcement and artifact reporting within the CI pipeline.
  - [ ] 9.3 Automate release packaging and PyPI publishing triggered by tagged releases.
