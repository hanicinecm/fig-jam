"""Story 2: section extraction works across formats."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from fig_jam import get_config


@pytest.mark.parametrize(
    ("filename", "contents", "expected"),
    [
        (
            "app_settings.json",
            """{
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
""",
            Path("/mnt/shared"),
        ),
        (
            "my_config.toml",
            """[nas_paths]
shared_drive_dir = "Z:\\\\shared\\\\path"
""",
            Path(r"Z:\shared\path"),
        ),
    ],
)
def test_story_02_section_extraction(
    write_config: Callable[[str, str], Path],
    filename: str,
    contents: str,
    expected: Path,
) -> None:
    """Extract the shared-drive section and coerce to Path."""
    write_config(filename, contents)

    result = get_config(
        section="nas_paths",
        validator={"shared_drive_dir": Path},
    )

    assert dict(result) == {"shared_drive_dir": expected}
