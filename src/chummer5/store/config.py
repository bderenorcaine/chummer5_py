"""Storage configuration, read from the environment (WP136)."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_CHARACTER_QUOTA = 100


def database_path() -> Path:
    """`CHUMMER5_DB`, else a per-user data file (`$XDG_DATA_HOME` or `~/.local/share`)."""
    explicit = os.environ.get("CHUMMER5_DB")
    if explicit:
        return Path(explicit)
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "chummer5" / "chummer5.db"


def character_quota() -> int:
    """`CHUMMER5_CHARACTER_QUOTA`, else 100 characters per account."""
    raw = os.environ.get("CHUMMER5_CHARACTER_QUOTA")
    if raw is None or not raw.strip():
        return DEFAULT_CHARACTER_QUOTA
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"CHUMMER5_CHARACTER_QUOTA must be an integer, got {raw!r}") from None
    if value < 0:
        raise ValueError("CHUMMER5_CHARACTER_QUOTA must not be negative")
    return value


# Not the 5 MB the plan first set: legacy saves embed their mugshots, and one in the test corpus
# (`Ghile Mear.chum5`) is 5.7 MB (decisions log, 2026-10-03). A native save is a few kilobytes.
DEFAULT_UPLOAD_MAX_MB = 10


def upload_max_bytes() -> int:
    """`CHUMMER5_UPLOAD_MAX_MB`, else 10: the largest file an upload may carry (WP140), in bytes.
    Read per request, like the quota."""
    raw = os.environ.get("CHUMMER5_UPLOAD_MAX_MB", "").strip()
    if not raw:
        return DEFAULT_UPLOAD_MAX_MB * 1024 * 1024
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"CHUMMER5_UPLOAD_MAX_MB must be a number, got {raw!r}") from None
    if value <= 0:
        raise ValueError(f"CHUMMER5_UPLOAD_MAX_MB must be above 0, got {raw!r}")
    return int(value * 1024 * 1024)
