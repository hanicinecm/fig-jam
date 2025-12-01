"""Shared fixtures for loader integration tests."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import pytest
from pydantic import BaseModel

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion


@dataclasses.dataclass
class DatabaseConfig:
    """Dataclass validator with an env override for password."""

    host: str
    port: int
    user: str = "admin"
    password: str = "changeme"  # noqa: S105
    __env_overrides__: ClassVar[dict[str, str]] = {"password": "APP_DB_PASSWORD"}


@dataclasses.dataclass
class ServiceConfig:
    """Nested dataclass validator for nested payloads."""

    database: DatabaseConfig
    region: str
    debug: bool = False


class PydanticDatabaseConfig(BaseModel):
    """Pydantic validator with an env override for password."""

    host: str
    port: int
    user: str = "admin"
    password: str
    __env_overrides__: ClassVar[dict[str, str]] = {"password": "PDB_PASSWORD"}


class PydanticServiceConfig(BaseModel):
    """Nested Pydantic validator."""

    database: PydanticDatabaseConfig
    region: str | None = None
    debug: bool = False


@pytest.fixture
def list_validator() -> list[str]:
    """List validator requiring host and port keys."""
    return ["host", "port"]


@pytest.fixture
def dict_validator() -> dict[str, type]:
    """Require host and port with types."""
    return {"host": str, "port": int}


@pytest.fixture
def dataclass_validator() -> type[DatabaseConfig]:
    """Dataclass validator for database settings."""
    return DatabaseConfig


@pytest.fixture
def nested_dataclass_validator() -> type[ServiceConfig]:
    """Nested dataclass validator for service settings."""
    return ServiceConfig


@pytest.fixture
def pydantic_validator() -> type[PydanticServiceConfig]:
    """Nested Pydantic validator for service settings."""
    return PydanticServiceConfig


@pytest.fixture
def write_json_config(tmp_path: Path) -> Callable[[str, dict[str, Any]], Path]:
    """Write a JSON config file to the tmp_path."""

    def _write(name: str, payload: dict[str, Any]) -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(payload))
        return path

    return _write


@pytest.fixture
def write_yaml_config(tmp_path: Path) -> Callable[[str, dict[str, Any]], Path]:
    """Write a YAML config file to the tmp_path."""

    def _write(name: str, payload: dict[str, Any]) -> Path:
        path = tmp_path / name
        path.write_text("\n".join(f"{key}: {value}" for key, value in payload.items()))
        return path

    return _write


@pytest.fixture
def write_toml_config(tmp_path: Path) -> Callable[[str, dict[str, Any]], Path]:
    """Write a TOML config file to the tmp_path."""

    def _write(name: str, payload: dict[str, Any]) -> Path:
        path = tmp_path / name
        lines = []
        for key, value in payload.items():
            if isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            else:
                lines.append(f"{key} = {value}")
        path.write_text("\n".join(lines))
        return path

    return _write


@pytest.fixture
def write_ini_config(tmp_path: Path) -> Callable[[str, dict[str, Any]], Path]:
    """Write an INI config file to the tmp_path."""

    def _write(name: str, payload: dict[str, Any]) -> Path:
        path = tmp_path / name
        lines = ["[DEFAULT]"]
        lines.extend(
            f"{key} = {value}"
            for key, value in payload.items()
            if not isinstance(value, dict)
        )
        for section, values in payload.items():
            if not isinstance(values, dict):
                continue
            lines.append(f"[{section}]")
            lines.extend(f"{k} = {v}" for k, v in values.items())
        path.write_text("\n".join(lines))
        return path

    return _write


@pytest.fixture
def config_dir_factory(
    tmp_path: Path, write_json_config: Callable[[str, dict[str, Any]], Path]
) -> Callable[[dict[str, dict[str, Any]]], Path]:
    """Create a directory populated with multiple JSON config files."""

    def _make(files: dict[str, dict[str, Any]]) -> Path:
        for name, payload in files.items():
            write_json_config(name, payload)
        return tmp_path

    return _make


@pytest.fixture
def assert_snapshot(
    snapshot: SnapshotAssertion, tmp_path: Path
) -> Callable[[str], None]:
    """Normalize temp paths before snapshot comparison."""

    def _assert(message: str) -> None:
        normalized = message.replace(str(tmp_path), "<tmp>")
        snapshot.assert_match(normalized)

    return _assert
