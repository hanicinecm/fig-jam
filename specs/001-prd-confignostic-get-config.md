# Fig-jam v1 PRD

## Overview

- **Name:** `fig-jam`
- **Description:** Single-call configuration loader that locates, parses, validates, and returns project settings across common formats without per-project boilerplate.
- **Scope:** Public API `fig_jam.get_config` and the supporting discovery, parsing, validation, and diagnostics internals required for v1.
- **Audience:** Python package maintainers who manage shared configuration data across many internal services or are just tired of writing boilerplate config extraction layers.

## Public API

The package exposes the following public interface through the `fig_jam` namespace:

### Functions

- **`get_config(path: Path | None = None, section: str | None = None, validator: Any = None, *, enable_overrides: bool = False) -> Any`**
  - Main entry point for configuration loading.
  - `path`: Optional path to a config file or directory. If `None`, searches user's home directory.
  - `section`: Optional top-level key to extract from config before validation.
  - `validator`: Optional schema for validation (Pydantic model, dataclass, `dict[str, type]`, or `list[str]`).
  - `enable_overrides`: When `True`, merges environment variables into parsed config before validation.
  - Returns validated configuration data in a format determined by the validator type:
    - `list[str]`: Returns a dict containing only the keys specified in the list (no type coercion).
    - `dict[str, type]`: Returns a dict containing only the keys specified in the dict, with values coerced to the specified types.
    - Dataclass or Pydantic model: Returns an instance of the validator type with coerced values.
    - `None` (no validator): Returns the raw parsed data as a dict with types determined by the parser.

### Exceptions

- **`ConfigSourceNotFoundError`**
  - Raised when no valid config files are found at the specified path.
  - Includes attempted paths and suggested config snippet based on validator.

- **`ConfigSourceAmbiguityError`**
  - Raised when multiple config files pass validation, making the selection ambiguous.
  - Lists all matching files with validation results to guide resolution.

- **`ConfigValidationError`**
  - Raised when a config file is found and parsed successfully, but fails validation.
  - Includes details about which fields are missing, have wrong types, or fail type coercion.
  - Provides suggestions for fixing the config or using environment variable overrides.

### Usage Example

```python
from fig_jam import get_config, ConfigSourceNotFoundError
from pathlib import Path

try:
    config = get_config(
        path=Path("./config"),
        section="database",
        validator={"host": str, "port": int},
        enable_overrides=True
    )
    print(config["host"], config["port"])
except ConfigSourceNotFoundError as e:
    print(f"Config not found: {e}")
```

## User Stories

### Story 1: Simple Config Discovery - Alice's Hobby Project

**Persona:** Alice, a solo developer working on a hobby Python project with a dedicated computer for running her application.

**Context:** Alice doesn't care about the exact config file path or format—she just wants her application to read configuration data without boilerplate. She expects there will be only one config file on her system.

**Workflow:**

1. **Initial attempt** - Alice writes minimal code to load config:

   ```python
   from fig_jam import get_config

   cfg_data = get_config()
   ```

2. **First run** - She runs the code on a fresh system and receives a `ConfigSourceNotFoundError` explaining that no config files were found in her home directory (the default path when `path=None`). The error message lists the attempted paths and supported file extensions (`.json`, `.toml`, `.yaml`, `.yml`, `.cfg`, `.ini`).

3. **Creating config** - Alice creates a file named `my_app_config.yaml` in her home directory with her settings:

   ```yaml
   host: alice
   password: "12345"
   ```

4. **Second run** - She runs her code again and receives a `ConfigSourceNotFoundError` with a different message: the YAML file was discovered but could not be parsed because the `pyyaml` dependency is not installed. The error includes installation instructions: `uv add pyyaml` or `pip install pyyaml`.

5. **Installing dependency** - Alice installs PyYAML using her preferred package manager.

6. **Success** - She runs her code one final time and it successfully returns:

   ```python
   {'host': 'alice', 'password': '12345'}
   ```

**Key takeaways:**

- No need to specify config filename—discovery finds any supported format automatically.
- Clear, actionable error messages guide the user through setup.
- Optional dependencies are only required when the corresponding file format is actually used.
- Zero boilerplate for simple use cases.

### Story 2: Section Extraction Across Formats - Bob's Shared Application

**Persona:** Bob, a developer at a small company building an application that will be used by all employees.

**Context:** Bob's application needs to read the path to the company NAS drive. He knows his coworkers already have various config files in their home directories with different structures and formats, but they all contain a `nas_paths` section with the required `shared_drive_dir` key. Bob wants his application to work with everyone's existing configs without requiring them to create new files or migrate formats.

**Existing configs:**

Zoran has `my_config.toml` in his home directory (`/home/zoran/`):

```toml
[nas_paths]
shared_drive_dir = "Z:\\shared\\path"
```

Wanda has `app_settings.json` in her home directory (`/home/wanda/`):

```json
{
  "database": {
    "host": "db.company.local",
    "port": 5432
  },
  "nas_paths": {
    "shared_drive_dir": "/mnt/shared/",
    "backup_dir": "/mnt/backup/"
  },
  "logging": {
    "level": "INFO"
  }
}
```

**Solution:**

Bob writes his application code using section extraction and validation:

```python
from fig_jam import get_config
from pathlib import Path

nas_config = get_config(
    section="nas_paths",
    validator={"shared_drive_dir": Path}
)

print(f"Config data: {nas_config}")
shared_drive = nas_config["shared_drive_dir"]
print(f"Using NAS drive at: {shared_drive}")
```

**Outcome:**

- Both Zoran and Wanda can run Bob's application without any changes to their existing config files.
- The `get_config` call discovers either TOML or JSON files in their respective home directories (since `path` was not specified, it defaults to the user's home directory).
- Section extraction pulls only the `nas_paths` section from the configs, ignoring other unrelated data.
- The validator ensures `shared_drive_dir` exists and coerces the string value to a `Path` object appropriate for their OS (Zoran sees `WindowsPath('Z:\\shared\\path')` on Windows, Wanda sees `PosixPath('/mnt/shared')` on Linux).
- Extra keys in the section (like Wanda's `backup_dir`) are filtered out.
- The application works seamlessly across different config formats, structures, and operating systems.

**Key takeaways:**

- Format-agnostic section extraction allows sharing applications across teams with heterogeneous config setups.
- Validation with type coercion (string → `Path`) ensures data comes out in the expected format.
- Users don't need to consolidate or standardize their config files—the library handles format differences.
- Unrelated config data in the same file is safely ignored.

### Story 3: Pydantic Validation with Defaults and Environment Overrides - Cilia's Database App

**Persona:** Cilia, a developer at the same company as Bob, building a Python application exclusively for Wanda.

**Context:** Cilia's application needs to extract database connection details (host, port, user, and password) from Wanda's existing `app_settings.json` config. She wants to use Pydantic for validation with sensible defaults where appropriate, but requires some fields (like password) to be explicitly provided.

**Wanda's existing config** (`/home/wanda/app_settings.json`):

```json
{
  "database": {
    "host": "db.company.local",
    "port": 5432
  },
  "nas_paths": {
    "shared_drive_dir": "/mnt/shared/",
    "backup_dir": "/mnt/backup/"
  },
  "logging": {
    "level": "INFO"
  }
}
```

**Solution:**

Cilia writes her application code with explicit path, section, and Pydantic validation:

```python
from fig_jam import get_config
from pathlib import Path
from pydantic import BaseModel


class DatabaseConfig(BaseModel):
    host: str
    port: int
    user: str = "admin"  # Default user
    password: str  # Required, no default


db_config = get_config(
    path=Path("/home/wanda/app_settings.json"),
    section="database",
    validator=DatabaseConfig,
    enable_overrides=True
)

print(f"Connecting to {db_config.host}:{db_config.port} as {db_config.user}")
```

**First run:**

When Wanda runs Cilia's app, she receives a `ConfigValidationError` with a message indicating that the required field `password` is missing from the `database` section in `/home/wanda/app_settings.json`. The error includes a suggestion to either add the field to the config or use an environment variable override.

**Resolution:**

Cilia sets the environment variable to provide the password without modifying the config file:

```bash
export FIG_JAM__DATABASE__PASSWORD="secure_db_pass"
```

Now when Wanda runs the application, it succeeds. The config is loaded with:

- `host` and `port` from the JSON file
- `user` defaulting to `"admin"` (from the Pydantic model)
- `password` from the environment variable

**Outcome:**

- Pydantic validation ensures type safety and provides clear error messages for missing required fields.
- Default values in the Pydantic model reduce boilerplate in config files.
- Environment variable overrides allow sensitive data (like passwords) to be provided without storing them in config files.
- The error message precisely identifies which field is missing and from which section/file.

**Key takeaways:**

- Pydantic models enable sophisticated validation with defaults, type coercion, and clear error messages.
- Environment overrides provide a secure way to supply sensitive configuration values.
- Explicit file paths eliminate ambiguity when working with known config locations.
- Validation errors reference the specific section and file, making debugging straightforward.

### Story 4: Disambiguation Through Validation - Dominic's Config Audit

**Persona:** Dominic, an IT manager at the same company, performing a config audit across employee machines.

**Context:** Dominic wants to check if any config files in Wanda's home directory contain a top-level `version` key with value `2`. He's working from a Python shell and wants to use `fig_jam` for this task without knowing exactly which config files exist or their formats.

**Wanda's home directory contains:**

- `my_config.toml` (Zoran's format, no version key)
- `app_settings.json` (contains various sections but no top-level version key)
- `system_config.json` (contains `{"version": 2, "system_name": "workstation-01", ...}`)

**Workflow:**

1. **First attempt** - Dominic tries the simplest call from Python shell:

   ```python
   >>> from fig_jam import get_config
   >>> from pathlib import Path
   >>> 
   >>> config = get_config(path=Path("/home/wanda"))
   ```

   He receives a `ConfigSourceAmbiguityError` indicating that multiple config files were found in `/home/wanda` (listing `my_config.toml`, `app_settings.json`, and `system_config.json`), and he needs to either specify an explicit file path or use a validator to disambiguate.

2. **Using validation to filter** - Dominic adds a dataclass validator that describes the structure he's looking for:

   ```python
   >>> from dataclasses import dataclass
   >>> 
   >>> @dataclass
   ... class VersionConfig:
   ...     version: int
   ... 
   >>> config = get_config(
   ...     path=Path("/home/wanda"),
   ...     validator=VersionConfig
   ... )
   >>> 
   >>> print(config)
   VersionConfig(version=2)
   >>> print(f"Found version {config.version}")
   Found version 2
   ```

**Outcome:**

- Without a validator, multiple configs caused ambiguity and raised `ConfigSourceAmbiguityError`.
- The dataclass validator filtered candidates: only `system_config.json` passed validation because it contained the required `version` key with an integer value.
- The other config files failed validation (missing `version` key or wrong type) and were eliminated, leaving exactly one valid candidate.
- Dominic successfully identified the config containing `version=2` without manually inspecting files.

**Key takeaways:**

- Validators serve dual purposes: validation and disambiguation when multiple config files exist.
- `ConfigSourceAmbiguityError` provides clear guidance when manual resolution is needed.
- Dataclass validators offer a lightweight alternative to Pydantic for simple validation scenarios.
- The validation-based filtering mechanism enables config discovery based on content structure, not just file names.

## Problem Statement / Why

- **Shared pain:** Internal teams repeatedly hand-roll config readers for identical data sources, causing drift, copy-pasted bugs, and unclear error messaging. A lot of boilerplate code is necessary to robustly code a config-reading layer with defaults, clear missing data messaging, etc.
- **Operational risk:** Missing or invalid configs break builds and deployments; current scripts fail silently or emit cryptic stack traces that slow incident response.
- **Constraints:** Solution must avoid mandatory third-party dependencies, support multiple config formats, and stay lightweight for broad reuse.

## Goals and Non-Goals

- **Goals:**
  - Deliver an intuitive API that discovers and parses JSON, TOML, YAML, and INI/CFG configs, with automatic format selection based on available dependencies.
  - Support validator types (Pydantic models, dataclasses, dict[str, type] specs, list[str] key selectors) to guarantee the presence of the data in the config and its shape.
  - Enforce deterministic discovery rules and produce actionable error guidance when configs are missing or invalid.
  - Offer optional environment-variable overrides for targeted keys before validation.
- **Non-goals:**
  - Building a CLI, daemon, or remote config service.
  - Recursing into subdirectories or non-filesystem sources (S3, Vault, secrets managers).
  - Shipping optional parsers/validators as bundled dependencies.
  - Supporting per-user override stacks or merge hierarchies beyond explicit environment overrides.
- **Success metrics:**
  - Full test coverage of supported formats and validator combinations.
  - 100% of negative-path tests verify that error messages describe corrective steps.

## Requirements / What

- **Functional requirements:**
  - Developer → calls `get_config(path, section=None, validator=None, *, enable_overrides=False)` → receives a validated result or a descriptive exception.
  - Developer → passes a directory path → loader inspects only top-level files of supported formats, applying validators and succeeding only when exactly one match remains.
  - Developer → passes `section` → loader extracts the top-level key before validation and return.
  - Developer → provides validator (Pydantic model, dataclass, dict[str, type], list[str]) → loader coerces/filters data accordingly and returns the coerced structure.
  - Developer → enables overrides → loader merges matching environment variables into parsed data prior to validation.
  - Developer → omits optional dependencies → loader skips unsupported formats/validators and raises `DependencyUnavailableError` with install instructions when needed.
- **Non-functional requirements:**
  - Pure-Python implementation with stdlib-only baseline; optional features rely on user-installed extras.
  - Compatible with CPython >=3.9; fully typed and mypy/pyright friendly.
  - Linted and formatted with `ruff`.
  - Thread-safe reads; repeated calls must remain side-effect free.
  - Works consistently across macOS, Linux, and Windows environments, including path handling and filesystem semantics.
  - Supports common text encodings across different operating systems:
    - Modern encodings: UTF-8 (primary), UTF-16, UTF-32 with BOM detection.
    - Legacy encodings: ASCII, Latin-1 (ISO-8859-1), Windows-1252 (CP1252), for backward compatibility with older config files.
    - Parsers attempt decoding with UTF-8 first, falling back to other encodings when necessary, with clear error messages on encoding failures.
  - Emits domain-specific exceptions (`ConfigSourceNotFoundError`, `ConfigSourceAmbiguityError`, `ConfigValidationError`).
  - Diagnostics include attempted paths, expected extensions, validator summary, encoding errors, and remediation hints.
  - Integrates with stdlib `logging` for traceability (debug-level discovery output).
  - Define module-level `__all__` only where namespace control is required (e.g., package `__init__` files) to avoid redundant lists that drift from the implementation.

## Design & Architecture / How

- **Module layout:**
  - `fig_jam.loader`: orchestrates the entire pipeline (discovery → validation → result extraction) and serves as the implementation for `get_config()`. Handles override integration and error surfacing.
  - `fig_jam.discovery`: takes `path` and `section` parameters and returns a structured object containing all candidate paths probed with their results. Internally invokes appropriate parsers from the parser registry for each candidate file. Each candidate contains either:
    - The parsed config data (as immutable mapping) or section content (if `section` was provided and found), or
    - An error describing what went wrong (file unreadable, invalid format, missing section, etc.). If a `section` is specified and not present in a candidate config, that candidate is rejected with a "section missing" error.
  - `fig_jam.parsers`: provides a registry mapping file suffixes to parser callables (JSON via `json`, TOML via `tomllib` for Python ≥3.11 or optional `tomli` for older versions, YAML via optional PyYAML, CFG via `configparser`). Each parser is a function that converts a `Path` to an immutable mapping, decorated with `register_parser(extensions: str | Iterable[str])` to self-register. Parsers are invoked by the discovery module, not directly by users.
  - `fig_jam.validation`: takes the output of `discovery` and filters candidates through the validator. Returns a structured object with all probed paths and their complete error history. For each candidate, the output contains either:
    - Validated data (format depends on validator type: dict, Pydantic model instance, dataclass instance, etc.), or
    - An error from any stage (parse failure, missing section, validation failure, etc.). Validation is only attempted on candidates that successfully passed discovery; earlier errors are preserved and passed through unchanged.
  - `fig_jam.overrides`: applies environment variable overrides using pattern `FIG_JAM__{SECTION?}__KEY` before validation.
  - `fig_jam.exceptions`: defines typed exceptions with docstrings describing remediation. Includes public exceptions (`ConfigSourceNotFoundError`, `ConfigSourceAmbiguityError`, `ConfigValidationError`) and internal ones (`DependencyUnavailableError` - public but not exposed in package namespace).
- **Data flow:**
  1. **Input normalization:** Convert inputs (`path`, optional `section`, validator reference, overrides flag) to canonical forms in `loader`.
  2. **Discovery stage (discovery):** Based on `path` (file or directory) and `section`, enumerate all candidate paths and invoke appropriate parsers from the parser registry for each candidate. If `section` is provided, extract section content from successfully parsed configs. Output is a structured object with all candidate paths and either their data (config or section content as immutable mapping) or errors (parse failure, decoding error, missing section, etc.).
  3. **Override stage (overrides, optional):** If `enable_overrides=True`, merge environment variables into successfully discovered mappings before validation proceeds. Candidates with errors from discovery are passed through unchanged.
  4. **Validation stage (validation):** Filter discovery results through the validator based on its type (Pydantic model, dataclass, `dict[str, type]`, `list[str]`, or `None`). Validation is only attempted on candidates with successful data from previous stages. Output is a structured object with all candidate paths preserving the complete error history—candidates may have parse errors, missing section errors, or new validation errors. Only candidates that passed all previous stages and validation contain validated data (type determined by validator).
  5. **Result extraction (loader):** Examine validation output. If exactly one candidate has valid data, return it. If zero candidates succeeded, raise `ConfigSourceNotFoundError` with full diagnostic information showing all attempted paths and their respective errors across all stages. If multiple candidates succeeded, raise `ConfigSourceAmbiguityError` listing all matching files. All error messages include comprehensive diagnostics from the entire pipeline.
- **Environment overrides:**
  - Disabled by default; optional boolean flag enables merge before validation.
  - Environment key syntax: `FIG_JAM__SECTION__FIELD` (if section) or `FIG_JAM__FIELD` (no section), case-insensitive.
  - Values use the same coercion logic as validator hints; type coercion failures raise `ConfigValidationError`.
- **Error guidance:**
  - Missing config: raise `ConfigSourceNotFoundError` with list of all attempted paths and detailed errors for each (parse failures, missing sections, validation failures). Include a generated sample config snippet based on validator keys.
  - Ambiguous matches: raise `ConfigSourceAmbiguityError` enumerating all files that passed validation, making the selection ambiguous.
  - Missing dependency: Private `DependencyUnavailableError` raised internally when optional parsers or validators are unavailable, containing `pip install` and `uv add` command hints. Surfaces through public exceptions with remediation guidance.

## Implementation Plan

Tests are written in parallel with each functional increment described below to keep coverage high and guide design.

1. **Foundation:**
   - Establish module skeletons (`exceptions.py`, `parsers.py`, `discovery.py`, `validation.py`, `loader.py`, `overrides.py`).
   - Define public API signatures, type hints, and docstrings in `loader.py`.
   - Define all exception classes in `exceptions.py` (public: `ConfigSourceNotFoundError`, `ConfigSourceAmbiguityError`, `ConfigValidationError`; internal: `DependencyUnavailableError` and other error types for parse failures, etc.).

2. **Parsers module:**
   - Implement parser registry with dynamic dependency detection (JSON via `json`, TOML via `tomllib` for Python ≥3.11 or optional `tomli` for older versions, YAML via optional PyYAML, CFG via `configparser`).
   - Each parser decorated with `register_parser(extensions: str | Iterable[str])` to self-register.
   - Each parser callable takes a `Path` and returns either parsed content (as immutable mapping via `types.MappingProxyType`) or raises an appropriate exception (parse failure, decoding error, missing dependency).
   - Implement encoding detection and fallback strategy:
     - Attempt UTF-8 decoding first (with BOM detection for UTF-16/UTF-32).
     - Fall back to legacy encodings (ASCII, Latin-1, Windows-1252) when UTF-8 fails.
     - Raise clear exceptions indicating encoding issues and attempted encodings when all fail.
   - Add unit tests for each parser with valid files, malformed files, missing dependency scenarios, and various encodings (UTF-8, UTF-16 with BOM, Latin-1, Windows-1252, mixed/invalid encodings).

3. **Discovery module:**
   - Implement path normalization (handle file vs. directory, `None` defaults to user's home directory).
   - Enumerate candidate paths based on registered parser extensions.
   - Invoke appropriate parsers for each candidate and collect results, catching exceptions and converting them to error records (including encoding errors with details about attempted encodings).
   - If `section` is provided, extract section content from successfully parsed configs. Candidates missing the specified section are rejected with a "section missing" error.
   - Return structured result object with all candidate paths and their outcomes (immutable mapping data or errors from parsing/encoding/section extraction).
   - Add unit tests for file input, directory input, section extraction, missing files, empty directories, parse failures, encoding failures, and missing sections.

4. **Validation module:**
   - Implement validator dispatcher for each supported type:
     - `None`: pass through data unchanged (returns dict with parser-determined types)
     - `list[str]`: filter to only specified keys, ensure all required keys present, return dict
     - `dict[str, type]`: coerce values to specified types (raising `ConfigValidationError` on coercion failure), ensure all keys present, filter to only specified keys, return dict
     - Dataclass: instantiate from mapping, allow extra fields in source data, return dataclass instance with coerced types
     - Pydantic model: validate via model constructor allowing extra fields, handle validation errors, return model instance
   - Take discovery output and process each candidate:
     - Candidates with errors from discovery stage are passed through unchanged (preserving parse errors, missing section errors, etc.).
     - Candidates with successful data are filtered through the validator; validation failures are converted to error records.
   - Return structured result object with all candidate paths preserving complete error history (parse errors, section errors, validation errors) alongside any successfully validated data.
   - Add unit tests for each validator type with valid/invalid data, optional dependency checks, and error preservation from earlier stages.

5. **Overrides module:**
   - Implement environment variable override merger.
   - Parse keys using pattern `FIG_JAM__{SECTION?}__KEY` (case-insensitive).
   - Merge into successfully discovered mappings before validation.
   - Add unit tests for override application with and without sections, key parsing, and type coercion.

6. **Loader module:**
   - Compose end-to-end `get_config()` function integrating all stages.
   - Examine validation output and enforce single-match invariant:
     - Zero valid candidates → raise `ConfigSourceNotFoundError` with full diagnostic info
     - One valid candidate → return it
     - Multiple valid candidates → raise `ConfigSourceAmbiguityError` listing all matches
   - Integrate stdlib `logging` for debug-level traceability (candidate enumeration, parse attempts, validation steps).
   - Add integration tests covering all error paths and success scenarios.

7. **Comprehensive testing:**
   - Author parametrized integration tests using fixture configs (JSON, TOML, YAML, CFG) across validator types.
   - Test section vs. no-section scenarios.
   - Test override combinations.
   - Verify all error messages include actionable remediation guidance.
   - Achieve 100% coverage on the `fig_jam` package.

8. **CI/CD setup:**
   - Configure GitHub Actions CI matrix across OS (Ubuntu, macOS, Windows) and Python versions (3.9+).
   - Run linting & formatting checks (`ruff check` and `ruff format --check`).
   - Run test suite (`pytest`) with coverage reporting.
   - Add version consistency check ensuring installed package version matches latest `CHANGELOG.md` entry.
   - Set up CD to publish to PyPI on GitHub releases with proper version tagging.

## Validation & Testing

- **Test strategy:**
  - **Unit tests:**
    - `parsers.py`: Each parser with valid files, malformed files, unsupported formats, decoding errors (UTF-8, UTF-16 with BOM, Latin-1, Windows-1252, invalid encodings), and missing dependencies.
    - `discovery.py`: File vs. directory input, section extraction, missing files, empty directories, multiple candidates, encoding failures.
    - `validation.py`: Each validator type (None, list, dict, dataclass, Pydantic) with valid/invalid data, missing fields, type coercion, optional dependencies.
    - `overrides.py`: Environment variable parsing, merging with/without sections, key case handling, type coercion.
    - `exceptions.py`: Exception instantiation and message formatting.
  - **Integration tests:**
    - Parametrized tests using fixture configs (JSON, TOML, YAML, CFG) across all validator types and section/no-section scenarios.
    - End-to-end `get_config()` flows covering success paths, `ConfigSourceNotFoundError`, `ConfigSourceAmbiguityError`, and `ConfigValidationError`.
    - Override integration with validation.
  - **Negative-path tests:**
    - Missing files: verify `ConfigSourceNotFoundError` with attempted paths and errors.
    - Multiple valid matches: verify `ConfigSourceAmbiguityError` with list of matching files.
    - Validation failures: verify errors include field mismatches and validator expectations.
    - Dependency absence: verify clear install instructions.
    - Parse failures: verify errors include file path and specific parse error.
    - Missing sections: verify errors indicate section not found in config.
- **Acceptance criteria:**
  - `pytest` suite passes with 100% coverage on the `fig_jam` package.
  - All negative-path tests confirm error messages include remediation guidance.
  - Structured result objects at each pipeline stage preserve full diagnostic context.
  - Documentation includes quick-start examples for each validator type and override usage.
  - `CHANGELOG.md` maintained with version history following semantic versioning.

## Appendices

- **Glossary:**
  - *Validator:* User-supplied schema or key selection that enforces config shape before return.
  - *Override:* Environment-provided value that replaces parsed config entries when enabled.
  - *Ambiguity:* More than one candidate config or section passes validation, requiring explicit resolution.
- **References:**
  - Python stdlib modules: `pathlib`, `json`, `configparser`, `tomllib` (Python ≥3.11).
  - Optional dependencies: `PyYAML`, `pydantic`, `tomli` (for Python <3.11).

## Future Work

### Config Caching

- Define a cache contract where every `get_config` call produces an immutable result (e.g., mapping proxies, frozen dataclasses, immutable Pydantic models) so cached objects can be returned directly without defensive copying.
- Formalize hashable identities for inputs: canonicalize paths, normalize section names, and derive stable fingerprints for validators (sorted key/type tuples for dict specs, reified field descriptors for dataclasses and Pydantic models).
- Once those guarantees are enforced, layer memoization atop `_load_config_internal`, expose cache controls or metrics as needed, and ensure invalidation hooks exist for runtime file changes or explicit user requests.
- Until then, document the residual risk that repeated calls re-read from disk so teams can decide whether to wrap `get_config` themselves.

### Configuration Blueprint Generation

- **Static call discovery:** Walk dependent codebases with `ast` or `libcst` to locate `fig_jam.get_config` invocations and capture literal arguments, flagging unresolved dynamic ones.
- **Validator inspection:** For list/dict validators, emit key/type expectations; import dataclasses to read `__dataclass_fields__`; load Pydantic v2 models to extract `model_fields`, including constraints such as bounds or regex patterns. Custom validators remain manual documentation tasks.
- **Aggregation model:** Group findings by canonical path and section, merge compatible validators, and highlight conflicts or mixed usage. Record whether overrides are enabled so environment variables can be documented.
- **Markdown generation:** Render the collected data into templated documentation—sections per config path, tables of fields and types, and warnings for dynamic or manual follow-up requirements. Provide both a CLI and library API so teams can integrate the crawler into CI or doc pipelines.
