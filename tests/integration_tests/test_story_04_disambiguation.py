"""Story 4: validation disambiguates multiple candidates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from fig_jam import ConfigSourceAmbiguityError, get_config


def test_story_04_disambiguation_with_dataclass(
    integration_home: Path,
    write_config: Callable[[str, str], Path],
) -> None:
    """Validate that dataclasses eliminate ambiguity when present."""
    write_config(
        "my_config.toml",
        """[feature]
name = "jam"
""",
    )
    write_config(
        "app_settings.json",
        """{
  "database": {
    "host": "db.company.local",
    "port": 5432
  }
}
""",
    )
    write_config(
        "system_config.json",
        """{
  "version": 2,
  "system_name": "workstation-01"
}
""",
    )

    with pytest.raises(ConfigSourceAmbiguityError) as excinfo:
        get_config(path=integration_home)
    expected_paths = {
        str(integration_home / "my_config.toml"),
        str(integration_home / "app_settings.json"),
        str(integration_home / "system_config.json"),
    }
    assert set(excinfo.value.context["matching_paths"]) == expected_paths

    @dataclass
    class VersionConfig:
        version: int

    result = get_config(path=integration_home, validator=VersionConfig)
    assert isinstance(result, VersionConfig)
    assert result.version == 2
