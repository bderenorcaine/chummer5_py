"""Backups of the database (WP142), taken and restored while the format stays SQLite's own.

**Taking one is safe while the server runs.** `backup` uses SQLite's online backup API (what the
`sqlite3` shell's `.backup` does): a consistent snapshot of the live database, WAL included, while
other connections keep reading and writing. The copy is switched out of WAL mode, so it is one
self-contained file, checked with `PRAGMA integrity_check`, and only then given its final name.
`keep` prunes the directory to the newest N backups.

**Restoring one is not.** `restore` overwrites the live database with a backup through the same
API (so the WAL and shared-memory files stay consistent; nothing has to be deleted by hand), and
must run with the server stopped: the running app holds chargen sessions whose next autosave
would conflict with the restored rows. It refuses a file that isn't a sound Chummer5 database or
whose schema is newer than this program knows. An older schema is migrated on the next start.

Both are reached through the admin CLI (`backup`, `restore`), and are plain functions so a later
admin page could call them.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from chummer5.store.migrations import MIGRATIONS, current_version
from chummer5.store.repository import Store

BACKUP_GLOB = "chummer5-*.db"
_BACKUP_NAME = re.compile(r"^chummer5-\d{8}-\d{6}(-\d+)?\.db$")


class BackupError(Exception):
    """A backup that couldn't be taken, or a file that can't be restored."""


def _check(db: sqlite3.Connection, what: str) -> None:
    result = db.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise BackupError(f"{what} fails SQLite's integrity check: {result}")


def _target(directory: Path, moment: datetime) -> Path:
    stem = f"chummer5-{moment.astimezone(UTC).strftime('%Y%m%d-%H%M%S')}"
    target = directory / f"{stem}.db"
    n = 1
    while target.exists():  # two backups within one second
        target = directory / f"{stem}-{n}.db"
        n += 1
    return target


def backups(directory: Path) -> list[Path]:
    """The backups `backup` wrote into `directory`, oldest first (their names sort by time)."""
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob(BACKUP_GLOB) if _BACKUP_NAME.match(p.name))


def backup(
    store: Store, directory: Path, *, keep: int | None = None, now: datetime | None = None
) -> Path:
    """Write a consistent copy of the live database to `directory` and return its path."""
    if keep is not None and keep < 1:
        raise BackupError("keep must be at least 1")
    store.initialize()  # a database that doesn't exist yet is created, then backed up empty
    directory.mkdir(parents=True, exist_ok=True)
    target = _target(directory, now or datetime.now(UTC))
    partial = target.with_name(target.name + ".partial")
    source = sqlite3.connect(store.path, timeout=30)
    try:
        copy = sqlite3.connect(partial)
        try:
            source.backup(copy)
            copy.execute("PRAGMA journal_mode = DELETE")  # one file, no -wal beside it
            _check(copy, "the new backup")
        finally:
            copy.close()
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    finally:
        source.close()
    partial.rename(target)
    if keep is not None:
        for old in backups(directory)[:-keep]:
            old.unlink()
    return target


def restore(store: Store, source: Path) -> int:
    """Replace the live database's contents with the backup at `source`. Returns the backup's
    schema version. Run it with the server stopped."""
    if not source.is_file():
        raise BackupError(f"no such file: {source}")
    try:
        backup_db = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise BackupError(f"{source} can't be opened: {exc}") from None
    try:
        try:
            _check(backup_db, str(source))
            version = current_version(backup_db)
        except sqlite3.DatabaseError as exc:
            raise BackupError(f"{source} is not an SQLite database: {exc}") from None
        if version == 0:
            raise BackupError(f"{source} is not a Chummer5 database (no schema version)")
        if version > len(MIGRATIONS):
            raise BackupError(
                f"{source} has schema version {version}, newer than this program knows "
                f"({len(MIGRATIONS)}); restore it with the version that wrote it"
            )
        store.path.parent.mkdir(parents=True, exist_ok=True)
        live = sqlite3.connect(store.path, timeout=30)
        try:
            backup_db.backup(live)
        finally:
            live.close()
    finally:
        backup_db.close()
    return version
