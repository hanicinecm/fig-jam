# Task List for Confignostic get_config Implementation

## Relevant Files

- `src/fig_jam/__init__.py` - Publish the public API (`get_config`, exceptions).
- `src/fig_jam/exceptions.py` - Define domain exceptions with remediation-focused messaging.
- `src/fig_jam/parsers.py` - House parser registry, format-specific parsers, and encoding handling.
- `src/fig_jam/discovery.py` - Implement candidate enumeration, parsing orchestration, and section extraction.
- `src/fig_jam/overrides.py` - Resolve validator-defined environment overrides prior to validation.
- `src/fig_jam/validation.py` - Validate parsed data against supported schema types.
- `src/fig_jam/loader.py` - Orchestrate the end-to-end load pipeline with logging and diagnostics.
- `tests/` - Mirror module structure with unit and integration coverage for the pipeline.
- `pyproject.toml` - Declare optional dependencies/extras and tooling configuration.
- `README.md` - Document quick-start usage, validators, and override examples.
- `.github/workflows/` - Host CI/CD automation definitions for linting, testing, and release.

## Tasks

- [x] 1 Establish module scaffolding and exported API surface.
  - [x] 1.1 Create module files with docstrings, type-hinted signatures, and placeholder implementations aligned with the architecture.
  - [x] 1.2 Implement domain exceptions structure and share remediation metadata across modules.
  - [x] 1.3 Update `src/fig_jam/__init__.py` to expose the public API
- [x] 2 Build parser registry with multi-encoding support and dependency gating.
  - [x] 2.1 Implement a `register_parser` decorator and central registry keyed by file suffix.
  - [x] 2.2 Implement JSON, TOML, INI/CFG, and YAML parsers with encoding fallbacks and optional dependency checks.
  - [x] 2.3 Emit structured parser results and dependency guidance for discovery and diagnostics layers.
- [x] 3 Implement discovery pipeline for candidate enumeration and section extraction.
  - [x] 3.1 Normalize input paths (file, directory, or defaults) and enumerate candidates with registered suffixes.
  - [x] 3.2 Invoke registered parsers, capturing successful data or error payloads without losing context.
  - [x] 3.3 Extract requested sections and annotate missing-section failures while preserving parsed data immutability guarantees.
- [x] 4 Implement validator-defined environment override resolution.
  - [x] 4.1 Validate `__env_overrides__` mappings to ensure keys reference known fields and values are environment variable names.
  - [x] 4.2 Resolve matching environment variables for dataclass and Pydantic validators prior to validation while surfacing unsupported override attempts.
- [x] 5 Deliver validator engine covering list, dict, dataclass, and Pydantic schemas.
  - [x] 5.1 Build validator dispatch plumbing that inspects the supplied schema type and routes accordingly.
  - [x] 5.2 Implement list/dict validators that perform key filtering, presence checks, and type coercion.
  - [x] 5.3 Integrate dataclass and Pydantic validation (with optional dependency loading) and normalize validation failures into diagnostic records.
- [x] 6 Compose `get_config` loader workflow with diagnostics, logging, and error shaping.
  - [x] 6.1 Orchestrate discovery and validation (including validator overrides) to return a single validated candidate.
  - [x] 6.2 Raise `ConfigSourceNotFoundError` or `ConfigSourceAmbiguityError` with aggregated diagnostics when invariants fail.
  - [x] 6.3 Emit debug-level logging for discovery attempts, parser selection, and validator outcomes.
- [ ] 7 Update packaging metadata and documentation to reflect new capabilities.
  - [ ] 7.1 Declare optional dependency extras and tooling configuration updates in `pyproject.toml`.
  - [ ] 7.2 Document API usage, validator patterns, and overrides in `README.md`.
  - [ ] 7.3 Align project metadata (e.g., classifiers, versioning notes) with the new feature set.
- [ ] 8 Configure CI/CD automation for linting, testing, coverage, and release publishing.
  - [ ] 8.1 Add GitHub Actions workflows covering linting, formatting, and test matrix execution.
  - [ ] 8.2 Integrate coverage enforcement and artifact reporting within the CI pipeline.
  - [ ] 8.3 Automate release packaging and PyPI publishing triggered by tagged releases.
