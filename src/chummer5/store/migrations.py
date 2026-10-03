"""Schema versioning (WP136): an ordered list of migrations applied at startup.

Each migration is a function taking an open connection inside a transaction. The list's index + 1
is the version it brings the schema to, so **append, never edit or reorder**. The current version
is held in the one-row `schema_version` table.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable


def _v1_initial(db: sqlite3.Connection) -> None:
    for statement in _V1_SCHEMA:
        db.execute(statement)


# One statement per entry: `executescript` would COMMIT implicitly and defeat the transaction.
_V1_SCHEMA = [
    """CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        created TEXT NOT NULL,
        last_login TEXT,
        theme TEXT,
        locale TEXT
    )""",
    """CREATE TABLE invite_codes (
        code TEXT PRIMARY KEY,
        created TEXT NOT NULL,
        expires TEXT,
        used_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        used_at TEXT
    )""",
    """CREATE TABLE auth_sessions (
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created TEXT NOT NULL,
        expires TEXT NOT NULL,
        last_seen TEXT NOT NULL
    )""",
    "CREATE INDEX auth_sessions_user ON auth_sessions(user_id)",
    """CREATE TABLE characters (
        id INTEGER PRIMARY KEY,
        owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        display_name TEXT NOT NULL DEFAULT '',
        street_name TEXT NOT NULL DEFAULT '',
        metatype TEXT NOT NULL DEFAULT '',
        save_json TEXT NOT NULL,
        revision INTEGER NOT NULL DEFAULT 1,
        created TEXT NOT NULL,
        updated TEXT NOT NULL
    )""",
    "CREATE INDEX characters_owner_updated ON characters(owner_id, updated DESC)",
]


MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [_v1_initial]


def current_version(db: sqlite3.Connection) -> int:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_version'"
    ).fetchone()
    if row is None:
        return 0
    found = db.execute("SELECT version FROM schema_version").fetchone()
    return int(found[0]) if found else 0


def migrate(db: sqlite3.Connection) -> None:
    """Bring the database to the latest schema. Safe to call on every start.

    The connection must be in autocommit mode (`isolation_level=None`). Each pending migration runs
    in its own transaction, so a failure leaves the schema at the last good version.
    """
    version = current_version(db)
    if version > len(MIGRATIONS):
        raise RuntimeError(
            f"database schema is version {version}, newer than this program knows "
            f"({len(MIGRATIONS)}); refusing to touch it"
        )
    for target in range(version + 1, len(MIGRATIONS) + 1):
        db.execute("BEGIN IMMEDIATE")
        try:
            # Re-check under the write lock: another process may have migrated meanwhile.
            if current_version(db) >= target:
                db.execute("ROLLBACK")
                continue
            MIGRATIONS[target - 1](db)
            db.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            db.execute("DELETE FROM schema_version")
            db.execute("INSERT INTO schema_version (version) VALUES (?)", (target,))
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
