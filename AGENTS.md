# Agent Playbook

## Mission Brief

- When in doubt, ask before making assumptions.
- Strive for elegant, Pythonic, and modular solutions.

## Project Layout

- Source code is located in `src/fig_jam/`, organized into logical modules or sub-packages.
- Tests are in `tests/` and mirror the source tree (e.g., `src/fig_jam/foo.py` → `tests/test_foo.py`).
- The project uses `uv` for environment management but must remain installable with `pip`.
- The Python virtual environment is in the `.venv/` directory and is managed by `uv`.

## Toolbelt

Note: All commands assume the virtual environment is active (`source .venv/bin/activate`).

- **Format and Lint**: `ruff check --fix && ruff format` (always format and lint the entire codebase).
- **Run tests**: `pytest`.
- **Install dependencies**: `uv add <pkg>` (or `uv add --dev <pkg>` for development dependencies).

## Coding Style and Standards

- Use 4-space indentation.
- Apply type hints everywhere, for both public and private interfaces.
- Write Google-style docstrings (without types; rely on hints) and document exceptions.
- Add module-level docstrings.
- Limit lines to 88 characters (the `black`/`ruff` default).
- Favor short, composable functions over deep inheritance.
- Prioritize readability over cleverness.
- Use concise comments for non-obvious code; avoid explaining the obvious.
- Prefer `pathlib` over `os` for path manipulation.
- Avoid relative imports.
- Define module-level `__all__` only where namespace control is required (e.g., package `__init__` files) to avoid redundant lists that drift from the implementation.

### Coding Style Examples

An example of a function docstring:

```python

def load_manifest(path: Path) -> Manifest:
  """Load a manifest file into memory.

  [Optional more detailed overview in several sentences/lines.]

  Args:
    path: Location of the manifest file.

  Returns:
    Parsed manifest instance.

  Raises:
    ManifestError: If the file is unreadable or malformed.
  """
  ...

```

## Testing Discipline

- Prefer test functions over test classes.
- Document each test function with a one-liner docstring (no need to adhere to the full Google-style format).
- Use `pytest` fixtures and organize shared fixtures in `conftest.py` modules.
- Parametrize tests to improve coverage.
- When asserting exceptions, use the `match` parameter of `pytest.raises` instead of inspecting the exception info.
- Maintain high test coverage on modified code; add tests for new or changed behavior unless instructed otherwise.

### Testing Examples

An example of fixtures in the project-level `conftest.py` module:

```python
# file: conftest.py

@pytest.fixture
def resources_dir() -> Path:
    """Get the path to the test resources directory."""
    return Path(__file__).parent / "resources"


@pytest.fixture
def fresh_resources_dir(resources_dir: Path, tmp_path: Path) -> Path:
    """Get a path to a fresh copy of the resources directory."""
    ...
```

An example of the correct usage of the `pytest.raises` context manager:

```python
# file: test_some_module.py

def test_some_function():
    """..."""
    with pytest.raises(ValueError, match=r"no such file exists"):
        check_file_exists()
```

## Git & Collaboration

- Never discard user changes. If conflicts arise, ask before rewriting.
- Do not commit unless asked.
- Use the Conventional Commits format: `<type>(<scope>): <description>`.
  - If the change closes a numbered task, reference it in the description.
  - Types include `feat`, `fix`, `test`, `refactor`, `docs`, and `chore`.
  - Example: `feat(cli): implement cli, close task 3.14`.
- **Branches**:
  - The `main` (or `master`) branch should not be touched by agents.
  - Development occurs on the `dev` branch or on feature branches.
- Document any residual risks or required manual checks in your summary.
