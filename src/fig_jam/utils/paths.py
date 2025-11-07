"""Helpers related to filesystem path handling."""

from __future__ import annotations

from pathlib import Path


def canonicalize_path(path: Path | None) -> Path:
    """Resolve a user-supplied path to a canonical absolute path.

    Args:
        path: Candidate path supplied by the caller or ``None`` to default to
            the user's home directory.

    Returns:
        Canonical path expanded for user directories and resolved when
        possible.
    """
    base = path if path is not None else Path.home()
    expanded = base.expanduser()
    try:
        return expanded.resolve()
    except OSError:
        return expanded
