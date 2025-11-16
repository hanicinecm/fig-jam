"""Story 1: simple config discovery highlights expected paths."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from fig_jam import ConfigSourceNotFoundError, get_config
from fig_jam.parsers import yaml_parser


def test_story_01_simple_config_discovery(
    integration_home: Path,
    write_config: Callable[[str, str], Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guide Alice from missing configs to a successful YAML load."""
    with pytest.raises(
        ConfigSourceNotFoundError,
        match=r"No configuration sources matched the requested criteria\.",
    ) as first_exc:
        get_config()
    assert str(integration_home) in first_exc.value.context["attempted_paths"]

    config_path = write_config(
        "my_app_config.yaml",
        """host: alice\npassword: "12345"\n""",
    )

    monkeypatch.setattr(yaml_parser, "yaml", None)
    with pytest.raises(
        ConfigSourceNotFoundError,
        match=r"No configuration sources matched the requested criteria\.",
    ) as second_exc:
        get_config()
    messages = {detail.message for detail in second_exc.value.diagnostics}
    assert "Optional dependency 'pyyaml' is not available." in messages
    assert str(config_path) in second_exc.value.context["attempted_paths"]
    monkeypatch.setattr(yaml_parser, "yaml", yaml)

    result = get_config()
    assert dict(result) == {"host": "alice", "password": "12345"}
