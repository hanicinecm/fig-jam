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


def normalize_extension(extension: str) -> str:
    """Normalize a file extension.

    Args:
        extension: File extension to normalize.

    Returns:
        Normalized file extension starting with a dot and in lowercase.
    """
    if not extension:
        message = "Parser extension cannot be empty."
        raise ValueError(message)
    normalized = extension if extension.startswith(".") else f".{extension}"
    return normalized.lower()
