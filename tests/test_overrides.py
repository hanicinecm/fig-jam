"""Tests for FIG_JAM environment overrides."""

from __future__ import annotations

from types import MappingProxyType

from fig_jam.overrides import apply_overrides


def test_apply_overrides_without_section() -> None:
    """Apply overrides when no section is specified."""
    data = MappingProxyType({"feature": {"name": "fig"}, "flag": False})
    environment = {"FIG_JAM__FEATURE__NAME": "jam"}

    outcome = apply_overrides(data, section=None, environment=environment)

    assert outcome.success is True
    assert outcome.data is not None
    assert outcome.data["feature"]["name"] == "jam"
    assert outcome.signature == (("FIG_JAM__FEATURE__NAME", "jam"),)
    assert outcome.diagnostics
    detail = outcome.diagnostics[0]
    assert detail.stage == "overrides.merge"


def test_apply_overrides_with_section() -> None:
    """Apply overrides scoped to a specified section."""
    data = MappingProxyType({"host": "localhost"})
    environment = {"FIG_JAM__DATABASE__PASSWORD": "secret"}

    outcome = apply_overrides(data, section="database", environment=environment)

    assert outcome.success is True
    assert outcome.data is not None
    assert outcome.data["password"] == "secret"  # noqa: S105 - test data
    assert outcome.signature == (("FIG_JAM__DATABASE__PASSWORD", "secret"),)


def test_apply_overrides_case_insensitive_matching() -> None:
    """Match keys in a case-insensitive manner."""
    data = MappingProxyType({"Feature": {"Name": "fig"}})
    environment = {"FIG_JAM__feature__name": "jam"}

    outcome = apply_overrides(data, section=None, environment=environment)

    assert outcome.success is True
    assert outcome.data is not None
    assert outcome.data["Feature"]["Name"] == "jam"
    assert outcome.signature == (("FIG_JAM__feature__name", "jam"),)


def test_apply_overrides_unsupported_path() -> None:
    """Reject overrides that target non-mapping parents."""
    data = MappingProxyType({"feature": "fig"})
    environment = {"FIG_JAM__FEATURE__NAME": "jam"}

    outcome = apply_overrides(data, section=None, environment=environment)

    assert outcome.success is False
    assert outcome.data is None
    assert outcome.diagnostics
    detail = outcome.diagnostics[0]
    assert "non-mapping" in detail.message
    assert outcome.signature == (("FIG_JAM__FEATURE__NAME", "jam"),)
