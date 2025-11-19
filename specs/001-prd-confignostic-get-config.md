# Fig-jam v1 PRD

## Overview

- **Name:** `fig-jam`
- **Description:** Single-call configuration loader that locates, parses, validates, and returns project settings across common formats without per-project boilerplate.
- **Scope:** Public API `fig_jam.get_config` and the supporting discovery, parsing, validation, and diagnostics internals required for v1.
- **Audience:** Python package maintainers who manage shared configuration data across many internal services or are just tired of writing boilerplate config extraction layers.

## Public API

The package exposes the following public interface through the `fig_jam` namespace:

### Functions

- **`get_config(path: Path | None = None, section: str | None = None, validator: Any = None) -> Any`**
  - Main entry point for configuration loading.
  - `path`: Optional path to a config file or directory. If `None`, searches user's home directory.
  - `section`: Optional top-level key to extract from config before validation.
  - `validator`: Optional schema for validation (Pydantic model, dataclass, `dict[str, type]`, or `list[str]`).
  - Returns validated configuration data in a format determined by the validator type:
    - `list[str]`: Returns a dict containing only the keys specified in the list (no type coercion).
    - `dict[str, type]`: Returns a dict containing only the keys specified in the dict, with values coerced to the specified types.
    - Dataclass or Pydantic model: Returns an instance of the validator type with coerced values. Validators may define a `__env_overrides__` mapping that the override stage uses to pull values from environment variables prior to validation.
    - `None` (no validator): Returns the raw parsed data as a dict with types determined by the parser.

### Exceptions

- **`ConfigError`**
  - A universal error raised in any case which does not lead to a single valid config found for the given `path`, `section` and `validator`.
  - The error can be raised for a variety of reasons:
    - No configuration file (with a supported suffix) is found for the given path.
    - No configuration file has been successfully decoded or parsed into the supported data structure.
    - No configuration file has passed the validation stage.
    - Etc.
  - The error message will always unambiguously state what is wrong and how to correct it.

### Usage Example

```python
from fig_jam import get_config, ConfigError
from pathlib import Path

try:
    config = get_config(
        path=Path("./config.yaml"),
        section="database",
        validator={"host": str, "port": int},
    )
    print(config["host"], config["port"])
except ConfigError as e:
    print(f"Config extraction failed with: {e}")
```

## Package Structure

The runtime package under `src/fig_jam/` is organized to keep responsibilities
modular and explicit:

```text
src/fig_jam
├── parsers/
│   ├── __init__.py
│   ├── _parsers_errors.py
│   ├── _parsers_utils.py
│   └── _parsers.py
└── pipeline/
    ├── __init__.py
    ├── _model.py
    ├── _validators.py
    ├── discover_sources.py
    ├── parse_sources.py
    ├── override_sources.py
    └── validate_sources.py
```

- The `parsers` package owns the registry of parsers defined for each suffix and
  exposes helpers for normalization, error handling, and supported suffix lookups.
- The `pipeline` package currently contains the state models (`_model`), validator
  introspection helpers (`_validators`), and the four stage implementations.
  Each stage module exposes one public function that accepts a `ConfigBatch` and
  returns the updated batch. Stages immediately return if `batch.error_code` is
  already set, so factories can instantiate a batch and bail out early when the
  root path or validator is invalid. These functions, along with `ConfigSource`,
  `ConfigBatch`, `BatchErrorCode`, and `PipelineStage`, are re-exported from the
  `fig_jam.pipeline` package for direct consumption.

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

2. **First run** - She runs the code on a fresh system and receives a `ConfigError` explaining that no config files were found in her home directory (the default path when `path=None`). The error message lists the attempted paths and supported file extensions (`.json`, `.toml`, `.yaml`, `.yml`, `.cfg`, `.ini`).

3. **Creating config** - Alice creates a file named `my_app_config.yaml` in her home directory with her settings:

   ```yaml
   host: alice
   password: "12345"
   ```

4. **Second run** - She runs her code again and receives a `ConfigError` with a different message: the YAML file was discovered but could not be parsed because the `pyyaml` dependency is not installed. The error includes installation instructions: `uv add pyyaml` or `pip install pyyaml`.

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
    __env_overrides__ = {"password": "APP_DB_PASSWORD"}


db_config = get_config(
    path=Path("/home/wanda/app_settings.json"),
    section="database",
    validator=DatabaseConfig,
)

print(f"Connecting to {db_config.host}:{db_config.port} as {db_config.user}")
```

**First run:**

When Wanda runs Cilia's app, she receives a `ConfigError` with a message indicating that the required field `password` is missing from the `database` section in `/home/wanda/app_settings.json`. The error suggests either adding the field to the config or setting the environment variable declared in `DatabaseConfig.__env_overrides__`.

**Resolution:**

Cilia sets the environment variable defined by the validator to provide the password without modifying the config file:

```bash
export APP_DB_PASSWORD="secure_db_pass"
```

Now when Wanda runs the application, it succeeds. The config is loaded with:

- `host` and `port` from the JSON file
- `user` defaulting to `"admin"` (from the Pydantic model)
- `password` from the environment variable

**Outcome:**

- Pydantic validation ensures type safety and provides clear error messages for missing required fields.
- Default values in the Pydantic model reduce boilerplate in config files.
- Validator-defined environment overrides allow sensitive data (like passwords) to be provided without storing them in config files.
- The error message precisely identifies which field is missing and from which section/file.

**Key takeaways:**

- Pydantic models enable sophisticated validation with defaults, type coercion, and clear error messages.
- Validator-defined environment overrides provide a secure way to supply sensitive configuration values.
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

   He receives a `ConfigError` indicating that multiple config files were found in `/home/wanda` (listing `my_config.toml`, `app_settings.json`, and `system_config.json`), and he needs to either specify an explicit file path or use a validator to disambiguate.

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

- Without a validator, multiple configs caused ambiguity and raised `ConfigError`.
- The dataclass validator filtered candidates: only `system_config.json` passed validation because it contained the required `version` key with an integer value.
- The other config files failed validation (missing `version` key or wrong type) and were eliminated, leaving exactly one valid candidate.
- Dominic successfully identified the config containing `version=2` without manually inspecting files.

**Key takeaways:**

- Validators serve dual purposes: validation and disambiguation when multiple config files exist.
- `ConfigError` provides clear guidance when manual resolution is needed.
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
  - Allow dataclass and Pydantic validators to opt into environment-driven overrides by declaring explicit `__env_overrides__` mappings.
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
  - Developer → calls `get_config(path, section=None, validator=None)` → receives a validated result or a descriptive exception.
  - Developer → passes a directory path → loader inspects only top-level files of supported formats, applying validators and succeeding only when exactly one match remains.
  - Developer → passes `section` → loader extracts the top-level key before validation and return.
  - Developer → provides validator (Pydantic model, dataclass, dict[str, type], list[str]) → loader coerces/filters data accordingly and returns the coerced structure.
  - Developer → declares `__env_overrides__` on dataclass or Pydantic validators → override stage pulls matching environment variables into the candidate data prior to validation.
  - Developer → omits optional dependencies → loader skips unsupported formats/validators and hints in a raised `ConfigError` that the path (or some paths) were skipped due to a missing dependency, with install instructions when needed. This applies to `yaml` format (requires `pyyaml`) or to `toml` format for older python without `tomllib` (requires `tomli`).
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
  - Emits a single universal exception, but with domain-specific verbose message with thorough diagnostics and proposed fixes.

## Design & Architecture / How

- **Data flow:**
  1. **Input normalization:** Convert inputs (`path`, optional `section`, validator reference) to canonical forms in `loader`.
  2. **Pipeline model instantiation:** Instantiate the pipeline `SourceBatch` object (I/O object for every stage of the pipeline), with all the initial validation (path has valid suffix, validator is correct type, env overrides are well defined, ...)
  3. **Discovery (`fig_jam.pipeline.discover`):** Based on `path` (file or directory), enumerate all candidate paths and instantiate the source objects to the batch, which will flow through the whole pipeline from now on.
  4. **Parsing (`fig_jam.pipeline.parse`):** Input is a list of source objects. Invoke appropriate parsers from the parser registry for each candidate and parse the files, or log errors to the source objects. If `section` is provided, extract section content from successfully parsed sources or log errors. Output is a list of modified source objects.
  5. **Override resolution (`fig_jam.pipeline.override`):** When a dataclass or Pydantic validator defines `__env_overrides__`, merge matching environment variables into the candidate data before validation. Only done on candiates (sources) which are still in the active game, while candidates with errors from prior stages are passed right through.
  6. **Validation stage (`fig_jam.pipeline.validate`):** Apply the user-provided validator (`None`, `list[str]`, `dict[str, type]`, dataclass, Pydantic model) to each acitive candidate. Candidates with prior errors are passed through unchanged. Successful candidates receive validated payloads; failures are logged.
  7. **Result extraction (loader):** Examine the objects passed through the pipeline. If exactly one candidate has valid data, return it. In any other case, the `ConfigError` is raised with all the appropriate context data.
- **Environment overrides:**
  - Disabled unless the validator (dataclass or Pydantic model) declares a `__env_overrides__` mapping.
  - `__env_overrides__` maps validator field names to environment variable names (strings). Keys must form a subset of the validator's fields.
  - Matching environment variables replace values in the candidate mapping prior to validation. Missing variables leave parsed values untouched. Applied overrides are plugged into the payload and logged in the objects passed through the pipeline.
- **Error guidance:**
  - The error messages are constucted by the exception itself, based on all the context data also passed to the exception.

## Pipeline Data Model

The pipeline flows `ConfigBatch` objects through four sequential stages: discovery, parsing, overrides, and validation. Each stage processes active sources (those without prior errors) and records stage status/metadata directly on the source objects for downstream diagnostics. All public stage functions, along with the `ConfigSource` and `ConfigBatch` models, are re-exported from the `fig_jam.pipeline` package namespace for convenient imports.

**ConfigSource (`fig_jam.pipeline._model`):** Represents a single candidate configuration file flowing through the pipeline.

- `path: Path` — Immutable file path discovered during the discovery stage.
- `raw_payload: MappingProxyType | None` — Frozen dict from the parser (immutable snapshot of parsed content).
- `payload: Any | None` — Working payload that evolves through stages; starts as a dict copy of `raw_payload` after parsing and may become a dataclass or Pydantic instance after validation.
- `applied_overrides: dict[str, str]` — Records which environment variables were applied, keyed by the dotted payload path (e.g., `"credentials.password" -> "APP_DB_PASSWORD"`). Only set if the values from ENV were *actually plugged* into the payload.
- `last_visited_stage: PipelineStage | None` — Enum value (`DISCOVER`, `PARSE`, `OVERRIDE`, `VALIDATE`) indicating the last stage this source reached, even if it failed.
- `stage_status: str | None` — Status code (per-stage enum value) reported by the last visited stage (e.g., `"success"`, `"missing-dependency-error"`).
- `stage_error_metadata: dict[str, Any]` — Free-form metadata specific to `stage_status`; includes diagnostics such as missing dependency name, exception object, or missing section name.

**ConfigBatch (`fig_jam.pipeline._model`):** Collection of `ConfigSource` objects flowing through the pipeline.

- `root_path: Path` — Original user-provided file or directory path. The suffix must be either empty, or one of the supported config formats, otherwise an error code is set.
- `section: str | None` — Original user-provided section name.
- `validator: list | dict[str, type] | dataclass | pydantic.BaseModel | None` — User-provided validator. Must be supported validator, otherwise an error code is set.
- `env_overrides: dict[tuple[str, ...], str]` — Unpacked *paths* through the validator's nested structure leading to an ENV_VAR names. Irrespective of if the enviroment variables actually exist or not. Parsed from static analysis of the validator (if dataclass or pydantic model). The overrides mapping on the model classes must be valid (defined for existing attribute names in the model classes), otherwise an appropriate error code is set.
- `sources: list[ConfigSource]` — List of candidate sources discovered and processed.
- `error_code: BatchErrorCode | None` — When discovery encounters a transport-level failure (unreadable path or non-file/directory), records the error and short-circuits the loader before further stages.

**BatchErrorCode (`fig_jam.pipeline._model`):**

```python
class BatchErrorCode(str, Enum):
  INVALID_PATH = "invalid-path"
  INVALID_VALIDATOR_TYPE = "invalid-validator-type"
  INVALID_ENV_OVERRIDE = "invalid-env-override"
```

<!-- ### Pipeline Stages

#### Stage 1: Discover

**Input:** `root_path` (file or directory).

**Output:** `ConfigBatch` either populated with candidate sources or short-circuited via `error_code` when resolution fails.

**Responsibilities:**

- If `root_path` is a file: create one `ConfigSource` for that path (even if the file/directory does not exist, in such case, an empty batch will be instantiated).
- If `root_path` is a directory: enumerate top-level files matching supported suffixes (`.json`, `.toml`, `.yaml`, `.yml`, `.cfg`, `.ini`), sorted deterministically, and create one `ConfigSource` per file.
- If `root_path` cannot be resolved because it does not exist, set `ConfigBatch.error_code` to `BatchErrorCode.PATH_NOT_FOUND`.
- If `root_path` cannot be resolved due to access restrictions or because it is neither a file nor a directory, set `ConfigBatch.error_code` to the appropriate `BatchErrorCode`.
- Set `last_visited_stage = PipelineStage.DISCOVER` on all sources that exist.
- Successful sources set `stage_status = DiscoverStatus.DISCOVERED` and empty `stage_error_metadata`.
- If `root_path` is a directory that exists but contains no supported config files, the batch is instantiated with an empty `sources` list and flows through the pipeline unchanged.

**Status Enum (`discover.py`):**

```python
class DiscoveryStatus(str, Enum):
  DISCOVERED = "discovered"
  PATH_NOT_ACCESSIBLE = "path-not-accessible"
```

**Error Metadata Examples:**

- `PATH_NOT_ACCESSIBLE`: `{"path": str(path), "reason": "permission denied"}`

#### Stage 2: Parse

**Input:** `ConfigBatch` with discovered sources (only active sources are processed).

**Output:** `ConfigBatch` with parsed payloads and recorded parse statuses.

**Responsibilities:**

- For each active source: determine parser by suffix; if dependency missing, record error status/metadata.
- Attempt decoding (UTF-8 first, fallbacks configured globally); on decoding failure, record metadata that includes `attempted_encodings`.
- Invoke parser to convert text to dict; ensure the parser result is a mapping, otherwise record type error.
- On success, populate both `raw_payload` (as `MappingProxyType`) and `payload` (as mutable dict copy).
- When `section` is provided, extract the top-level key from `payload` and treat it as the new payload; missing section triggers `MISSING_SECTION_ERROR`.
- Set `last_visited_stage = PipelineStage.PARSE` on each processed source and assign per-source `stage_status`/`stage_error_metadata`.

**Status Enum (`parse.py`):**

```python
class ParsingStatus(str, Enum):
  PARSED = "parsed"
  MISSING_DEPENDENCY_ERROR = "missing-dependency-error"
  DECODING_ERROR = "decoding-error"
  SYNTAX_ERROR = "syntax-error"
  TYPE_ERROR = "type-error"
  MISSING_SECTION_ERROR = "missing-section-error"
```

**Error Metadata Examples:**

- `MISSING_DEPENDENCY_ERROR`: `{"dependency": "pyyaml", "hint": "uv add pyyaml"}`
- `DECODING_ERROR`: `{"attempted_encodings": ["utf-8", "latin-1"], "reason": "..."}`
- `SYNTAX_ERROR`: `{"message": "Invalid YAML", "line": 5, "column": 10, "exception": <exc>}`
- `TYPE_ERROR`: `{"expected": "mapping", "actual": "list"}`
- `MISSING_SECTION_ERROR`: `{"section": "database", "available_keys": ["logging"]}`

#### Stage 3: Override

**Input:** Parsed `ConfigBatch` plus optional validator reference.

**Output:** ConfigBatch with overrides applied to payloads.

**Responsibilities:**

- Only active sources are amended.
- When the validator (dataclass or Pydantic model) defines `__env_overrides__`, traverse the payload using dot-notation paths derived from the validator hierarchy to apply env vars. The `__env_overrides__` mapping always uses local field names of that validator type (never dotted paths); dotted paths such as `"credentials.password"` are only used for the `applied_overrides` keys stored on `ConfigSource`.
- If the env var is present, inject it into the payload and record the dotted path → env var name mapping inside `applied_overrides`.
- Assign `OverrideStatus.NOT_CONFIGURED` when no validator or no mapping exists, `OverrideStatus.CONFIGURED` whenever a mapping is present and processed (even if no env var applies) and `OverrideStatus.FIELD_ERROR` when the mapping references a field not present in the validator payload. `stage_error_metadata` captures the missing path.
- Set `last_visited_stage = PipelineStage.OVERRIDE` and update `stage_status`/`stage_error_metadata`.

**Status Enum (`override.py`):**

```python
class OverridesStatus(str, Enum):
  CONFIGURED = "configured"
  NOT_CONFIGURED = "not-configured"
  FIELD_ERROR = "field-error"
```

**Error Metadata Examples:**

- `FIELD_ERROR`: `{"path": "credentials.password", "validator_field": "password"}`

**Example:** When a validator defines nested dataclasses (e.g., `DatabaseConfig` contains `credentials: Credentials`) and only `Credentials` declares `__env_overrides__ = {"password": "APP_DB_PASSWORD"}`, the override stage records `applied_overrides = {"credentials.password": "APP_DB_PASSWORD"}` while `OverrideStatus.CONFIGURED` signals that overrides were considered.

#### Stage 4: Validate

**Input:** Overridden `ConfigBatch` plus validator.

**Output:** Finalized `ConfigBatch` containing source(s) with validated coerced payload(s).

**Responsibilities:**

- Only active sources are validated.
- When the validator is `None`, mark sources with `ValidateStatus.NO_VALIDATOR` and leave payload as-is.
- When validator is `list[str]`, filter payload to the listed keys without any type coercion and set status to `VALIDATED` or `VALIDATION_ERROR` as needed.
- When validator is `dict[str, type]`, it must always be a mapping from `str` to a concrete type. Filter payload to the listed keys, coercing values to the declared types (including collections such as `list`, where element types are not enforced and depend entirely on the config content and parser), and set status to `VALIDATED` or `VALIDATION_ERROR` as needed.
- When validator is a dataclass or Pydantic model type, instantiate it with the payload, replace `payload` with the validated result, or record validation error metadata on failure. The `ConfigBatch.validator` attribute always holds the validator type, not an instance.
- Always update `last_visited_stage = PipelineStage.VALIDATE` and record `stage_status`/`stage_error_metadata` for each source.

**Status Enum (`validate.py`):**

```python
class ValidationStatus(str, Enum):
  NO_VALIDATOR = "no-validator"
  VALIDATED = "validated"
  VALIDATION_ERROR = "validation-error"
```

**Error Metadata Examples:**

- `VALIDATION_ERROR`: `{"message": "...", "exception": <exc>}` -->

### Result Extraction (Loader)

- After validation, the loader first checks `ConfigBatch.error_code`. If present, the loader raises immediately without examining sources.
- Otherwise, it pushes the batch through the pipeline stage by stage until done.
- After the batch squeezes through the complete pipeline:
  - When exactly one source is validated without validation error, return its `payload`.
  - When zero sources succeeds (either never reach the validation stage, or end up with validation errors), or if more than a single source succeeds, raise a `ConfigError` with the batch saved in the exception as an attribute.
- The batch will provide sufficiant context for the exception to compose a helpful message with hints etc, so we can easily get away with a single error type.

### Error Flow and Diagnostics

- Each source tracks the final stage it reached, allowing errors to be attributed to a specific stage (discover/parse/override/validate).
- Downstream stages skip inactive sources, keeping diagnostics localized to the first failure.
- The final `ConfigError` message uses the accumulated `stage_status`/`stage_error_metadata` per source so users see exactly which parser, env var, or validator requirement failed.

## CI/CD setup

- Configure GitHub Actions CI matrix across OS (Ubuntu, macOS, Windows) and Python versions (3.9+).
- Run linting & formatting checks (`ruff check` and `ruff format --check`).
- Run test suite (`pytest`) with coverage reporting.
- Add version consistency check ensuring installed package version matches latest `CHANGELOG.md` entry.
- Set up CD to publish to PyPI on GitHub releases with proper version tagging.

## Appendices

- **Glossary:**
  - *Validator:* User-supplied schema or key selection that enforces config shape before return.
  - *Override:* Environment-provided value that replaces parsed config entries when a validator declares a `__env_overrides__` mapping.
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
- **Aggregation model:** Group findings by canonical path and section, merge compatible validators, and highlight conflicts or mixed usage. Record whether validators declare `__env_overrides__` so environment variables can be documented.
- **Markdown generation:** Render the collected data into templated documentation—sections per config path, tables of fields and types, and warnings for dynamic or manual follow-up requirements. Provide both a CLI and library API so teams can integrate the crawler into CI or doc pipelines. Triggered from CLI, printed to stdout.
- **Template generation:** Render the collected data into a configuration template of the requested format, with default values filled in and required values filled with obvious placeholders. Triggered from CLI, printed to stdout.

### Diagnostics & Logging

- Define an optional logging surface that mirrors the pipeline diagnostics (discovery/parse/overrides/validation stages) so operators can trace candidate handling at debug level without enabling exceptions.
- Log candidate enumeration counts, parser format/encoding attempts, override resolution events, and validation successes/failures alongside metadata like paths and validator summaries so logs can correlate with eventual diagnostics.
- Document how to configure `logging` (handlers, log levels) to capture these records and highlight that this telemetry is deferred until future work to keep the current release lean.
