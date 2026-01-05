"""Integration tests for the public get_config API."""

from __future__ import annotations

import dataclasses
import importlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

import pytest

from fig_jam import ConfigError, get_config
from tests.integration_tests.conftest import (
    DatabaseConfig,
    PydanticServiceConfig,
    ServiceConfig,
)


def test_list_validator_filters_payload(
    write_json_config: Callable[[str, dict[str, Any]], Path],
    list_validator: list[str],
) -> None:
    """Return filtered mapping when using list validator."""
    path = write_json_config(
        "config.json", {"host": "localhost", "port": 5432, "extra": "ignored"}
    )

    result = get_config(path=path, validator=list_validator)

    assert result == {"host": "localhost", "port": 5432}


def test_directory_disambiguates_candidates(
    write_json_config: Callable[[str, dict[str, Any]], Path],
    list_validator: list[str],
) -> None:
    """Choose the only candidate that satisfies the validator."""
    valid = write_json_config("valid.json", {"host": "db", "port": 5432})
    invalid = write_json_config("invalid.json", {"host": "db"})
    root = Path(valid).parent

    result = get_config(path=root, validator=list_validator)

    assert result == {"host": "db", "port": 5432}
    assert result != json.loads(invalid.read_text())


def test_dataclass_validator_applies_env_override(
    write_json_config: Callable[[str, dict[str, Any]], Path],
    nested_dataclass_validator: type[ServiceConfig],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apply env override before dataclass validation."""
    expected = "from-env"
    monkeypatch.setenv("APP_DB_PASSWORD", expected)
    path = write_json_config(
        "service.json",
        {
            "database": {"host": "db", "port": 5432, "user": "svc"},
            "region": "us-east-1",
        },
    )

    result = get_config(path=path, validator=nested_dataclass_validator)

    assert isinstance(result, ServiceConfig)
    assert isinstance(result.database, DatabaseConfig)
    assert result.database.password == expected


def test_missing_section_snapshot(
    write_json_config: Callable[[str, dict[str, Any]], Path],
    dict_validator: dict[str, type],
    assert_snapshot: Callable[[str], None],
) -> None:
    """Snapshot missing section message."""
    path = write_json_config("config.json", {"host": "db", "port": 5432})

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path, section="database", validator=dict_validator)

    assert_snapshot(str(excinfo.value))


def test_missing_keys_snapshot(
    write_json_config: Callable[[str, dict[str, Any]], Path],
    dict_validator: dict[str, type],
    assert_snapshot: Callable[[str], None],
) -> None:
    """Snapshot missing keys message."""
    path = write_json_config("config.json", {"host": "db"})

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path, validator=dict_validator)

    assert_snapshot(str(excinfo.value))


def test_multiple_validated_sources_snapshot(
    write_json_config: Callable[[str, dict[str, Any]], Path],
    list_validator: list[str],
    assert_snapshot: Callable[[str], None],
) -> None:
    """Snapshot multiple validated candidates message."""
    first = write_json_config("a.json", {"host": "db-a", "port": 1111})
    write_json_config("b.json", {"host": "db-b", "port": 2222})
    root = Path(first).parent

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=root, validator=list_validator)

    assert_snapshot(str(excinfo.value))


def test_pydantic_validation_error_snapshot(
    write_json_config: Callable[[str, dict[str, Any]], Path],
    pydantic_validator: type[PydanticServiceConfig],
    assert_snapshot: Callable[[str], None],
) -> None:
    """Snapshot pydantic validation failure."""
    path = write_json_config(
        "service.json",
        {"database": {"host": "db", "port": 5432, "user": "svc"}},
    )

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path, validator=pydantic_validator)

    assert_snapshot(str(excinfo.value))


def test_yaml_missing_dependency_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    assert_snapshot: Callable[[str], None],
    list_validator: list[str],
) -> None:
    """Snapshot missing dependency message when YAML loader unavailable."""
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("host: db\nport: 5432\n")
    monkeypatch.setattr("fig_jam.parsers._parsers.yaml", None)

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=yaml_path, validator=list_validator)

    assert_snapshot(str(excinfo.value))


def test_no_sources_snapshot(
    tmp_path: Path, assert_snapshot: Callable[[str], None]
) -> None:
    """Snapshot message when directory has no configs."""
    empty_dir = tmp_path / "configs"
    empty_dir.mkdir()

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=empty_dir)

    assert_snapshot(str(excinfo.value))


def test_path_not_found_snapshot(
    tmp_path: Path, assert_snapshot: Callable[[str], None]
) -> None:
    """Snapshot missing path discovery error."""
    missing = tmp_path / "missing.json"

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=missing)

    assert_snapshot(str(excinfo.value))


def test_unsupported_format_snapshot(
    tmp_path: Path, assert_snapshot: Callable[[str], None]
) -> None:
    """Snapshot unsupported format batch error."""
    path = tmp_path / "config.txt"
    path.write_text("data")

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path)

    assert_snapshot(str(excinfo.value))


def test_invalid_validator_type_snapshot(
    tmp_path: Path, assert_snapshot: Callable[[str], None]
) -> None:
    """Snapshot invalid validator type."""
    path = tmp_path / "config.json"
    path.write_text('{"key": "value"}')

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path, validator=42)

    assert_snapshot(str(excinfo.value))


def test_invalid_env_override_snapshot(assert_snapshot: Callable[[str], None]) -> None:
    """Snapshot invalid env override declaration."""

    @dataclasses.dataclass
    class InvalidOverride:
        name: str
        __env_overrides__: ClassVar[dict[str, str]] = {"missing": "ENV_VAR"}  # type: ignore[var-annotated]

    with pytest.raises(ConfigError) as excinfo:
        get_config(validator=InvalidOverride)

    assert_snapshot(str(excinfo.value))


def test_invalid_strict_snapshot(
    write_json_config: Callable[[str, dict[str, Any]], Path],
    dict_validator: dict[str, type],
    assert_snapshot: Callable[[str], None],
) -> None:
    """Snapshot invalid strict value with dict validator."""
    path = write_json_config("config.json", {"host": "db", "port": "abc"})

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path, validator=dict_validator, strict=False)

    assert_snapshot(str(excinfo.value))


def test_syntax_error_snapshot(
    tmp_path: Path, assert_snapshot: Callable[[str], None]
) -> None:
    """Snapshot parse syntax error."""
    path = tmp_path / "broken.json"
    path.write_text('{"host": "db",}')

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path)

    assert_snapshot(str(excinfo.value))


def test_not_mapping_snapshot(
    tmp_path: Path, assert_snapshot: Callable[[str], None]
) -> None:
    """Snapshot parse not-mapping error."""
    path = tmp_path / "list.json"
    path.write_text('["a", "b"]')

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path)

    assert_snapshot(str(excinfo.value))


def test_validation_type_coercion_snapshot(
    write_json_config: Callable[[str, dict[str, Any]], Path],
    dict_validator: dict[str, type],
    assert_snapshot: Callable[[str], None],
) -> None:
    """Snapshot type coercion failure."""
    path = write_json_config("config.json", {"host": "db", "port": "not-an-int"})

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path, validator=dict_validator)

    assert_snapshot(str(excinfo.value))


def test_dataclass_missing_required_snapshot(
    write_json_config: Callable[[str, dict[str, Any]], Path],
    dataclass_validator: type[DatabaseConfig],
    assert_snapshot: Callable[[str], None],
) -> None:
    """Snapshot dataclass instantiation failure for missing field."""
    path = write_json_config("config.json", {"host": "db"})

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path, validator=dataclass_validator)

    assert_snapshot(str(excinfo.value))


def test_list_missing_keys_snapshot(
    write_json_config: Callable[[str, dict[str, Any]], Path],
    list_validator: list[str],
    assert_snapshot: Callable[[str], None],
) -> None:
    """Snapshot list validator missing keys."""
    path = write_json_config("config.json", {"host": "db"})

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path, validator=list_validator)

    assert_snapshot(str(excinfo.value))


def test_template_yaml_format(
    write_yaml_config: Callable[[str, dict[str, Any]], Path],
    dict_validator: dict[str, type],
    assert_snapshot: Callable[[str], None],
) -> None:
    """Snapshot template rendering in YAML format."""
    path = write_yaml_config("config.yaml", {"host": "db"})

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path, validator=dict_validator)

    assert_snapshot(str(excinfo.value))


def test_template_toml_format(
    write_toml_config: Callable[[str, dict[str, Any]], Path],
    dict_validator: dict[str, type],
    assert_snapshot: Callable[[str], None],
) -> None:
    """Snapshot template rendering in TOML format."""
    if (
        importlib.util.find_spec("tomllib") is None
        and importlib.util.find_spec("tomli") is None
    ):
        pytest.skip("TOML support not available")
    path = write_toml_config("config.toml", {"host": "db"})

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path, validator=dict_validator)

    assert_snapshot(str(excinfo.value))


def test_template_ini_format(
    write_ini_config: Callable[[str, dict[str, Any]], Path],
    dict_validator: dict[str, type],
    assert_snapshot: Callable[[str], None],
) -> None:
    """Snapshot template rendering in INI format."""
    path = write_ini_config("config.ini", {"host": "db"})

    with pytest.raises(ConfigError) as excinfo:
        get_config(path=path, section="DEFAULT", validator=dict_validator)

    assert_snapshot(str(excinfo.value))


def test_yaml_success(
    write_yaml_config: Callable[[str, dict[str, Any]], Path],
    dict_validator: dict[str, type],
) -> None:
    """Load YAML config successfully."""
    path = write_yaml_config("config.yaml", {"host": "db", "port": 5432})

    result = get_config(path=path, validator=dict_validator)

    assert result == {"host": "db", "port": 5432}


def test_toml_success(
    write_toml_config: Callable[[str, dict[str, Any]], Path],
    dict_validator: dict[str, type],
) -> None:
    """Load TOML config successfully."""
    if (
        importlib.util.find_spec("tomllib") is None
        and importlib.util.find_spec("tomli") is None
    ):
        pytest.skip("TOML support not available")
    path = write_toml_config("config.toml", {"host": "db", "port": 5432})

    result = get_config(path=path, validator=dict_validator)

    assert result == {"host": "db", "port": 5432}


def test_ini_success(
    write_ini_config: Callable[[str, dict[str, Any]], Path],
) -> None:
    """Load INI config successfully."""
    path = write_ini_config("config.ini", {"host": "db", "port": 5432})

    result = get_config(path=path, section="DEFAULT")

    assert result == {"host": "db", "port": "5432"}


def test_directory_with_multiple_formats(
    tmp_path: Path,
    list_validator: list[str],
) -> None:
    """Choose correct source among mixed formats."""
    json_path = tmp_path / "config.json"
    json_path.write_text('{"host": "db-json", "port": 1111}')
    toml_path = tmp_path / "config.toml"
    toml_path.write_text('host = "db-toml"\nport = 2222')

    with pytest.raises(ConfigError):
        get_config(path=tmp_path, validator=list_validator)


def test_file_access_error_snapshot(
    tmp_path: Path,
    assert_snapshot: Callable[[str], None],
) -> None:
    """Snapshot file access error."""
    path = tmp_path / "config.json"
    path.write_text('{"host": "db"}')
    path.chmod(0o000)

    try:
        with pytest.raises(ConfigError) as excinfo:
            get_config(path=path)
    finally:
        path.chmod(0o644)

    assert_snapshot(str(excinfo.value))
