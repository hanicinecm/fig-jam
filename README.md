# `fig-jam`

[![CI status](https://github.com/hanicinecm/fig-jam/actions/workflows/ci.yaml/badge.svg)](https://github.com/hanicinecm/fig-jam/actions/workflows/ci.yaml)
[![codecov](https://codecov.io/github/hanicinecm/fig-jam/graph/badge.svg?token=542NGCYIDW)](https://codecov.io/github/hanicinecm/fig-jam)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/fig-jam.svg)
[![PyPI](https://img.shields.io/pypi/v/fig-jam.svg)](https://pypi.org/project/fig-jam/)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/format.json)](https://github.com/astral-sh/ruff)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

Single-call configuration loader that discovers, parses, validates, and documents
project settings with minimal boilerplate.

## Quick start

```python
from fig_jam import get_config

config = get_config(
    path="./config.yaml",                  # file or directory; defaults to ~
    section="database",                    # optional top-level key to extract
    validator={"host": str, "port": int},  # or list[str], dataclass, Pydantic
)

print(config)                              # {"host": "127.0.0.1", "port": 8050}
```

`get_config` returns validated data when exactly one candidate succeeds, otherwise
raises `ConfigError` with actionable guidance and a suggested config template.

## What it does

- Discovers config files when given a directory; chooses the sole candidate that
  passes validation, or asks you to disambiguate.
- Parses common formats: JSON; INI/CFG; TOML via `tomllib`/`tomli`; YAML via
  `pyyaml`. Files are decoded with BOM-aware UTF-8 fallback to ASCII/Latin-1/CP1252.
- Applies environment overrides declared on dataclass or Pydantic validators via
  `__env_overrides__ = {"field": "ENV_VAR"}` before validation.
- Validates payloads using:
  - `None`: return raw mapping.
  - `list[str]`: assert keys exist; `strict=True` (default) filters to those keys.
  - `dict[str, type]`: assert keys exist, coerce types, return filtered mapping.
  - Dataclass: coerce field types (including nested dataclasses/models) and
    instantiate.
  - Pydantic model: let Pydantic validate and instantiate.
- `strict` must stay `True` for dict/dataclass/Pydantic validators; may be set to
  `False` with a list validator to keep extra keys.

## Why it’s helpful

- Zero per-project parser setup—formats are auto-detected and optional
  dependencies are only required when their formats are present.
- Clear `ConfigError` messages capture discovery, parsing, overrides, and
  validation diagnostics so you know what to fix next.
- Built-in template rendering shows the expected shape (and env vars) for the
  current validator and file format.
