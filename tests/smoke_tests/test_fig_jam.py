"""A high-level smoke test for the build process."""

from __future__ import annotations

from pathlib import Path

import pytest

import fig_jam
from fig_jam import get_config


@pytest.fixture
def nested_toml_config(tmp_path: Path) -> Path:
    """Create a nested TOML config file and return its path."""
    config_path = tmp_path / "config.toml"
    config_lines = [
        "[service]",
        'name = "fig-jam"',
        "debug = true",
        "",
        "[service.features]",
        "enabled = true",
        'mode = "safe"',
        "retries = 3",
    ]
    config_path.write_text("\n".join(config_lines))
    return config_path


def test_package_version() -> None:
    """Expose a non-empty package version."""
    assert isinstance(fig_jam.__version__, str)
    assert fig_jam.__version__


def test_get_config_loads_dataclass(nested_toml_config: Path) -> None:
    """Parse a nested TOML config, no validators, no nothing..."""
    result = get_config(path=nested_toml_config, section="service")

    expected = {
        "name": "fig-jam",
        "debug": True,
        "features": {"enabled": True, "mode": "safe", "retries": 3},
    }

    assert result == expected
