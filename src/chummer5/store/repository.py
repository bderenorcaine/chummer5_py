"""The repository (WP136): every database access the web layer and the admin CLI make.

**Short-lived connections.** Each method opens a connection, does its work in one transaction and
closes it, so nothing is shared between the request threads. The connection is in autocommit mode
and transactions are explicit, which keeps `BEGIN IMMEDIATE` (a write lock taken up front) possible
for the read-then-write sequences (quota check, revision check).

**Owner scoping.** Every character method takes `owner_id` and puts it in the `WHERE` clause, so a
guessed ID of someone else's character is "not found", indistinguishable from a missing one.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from chummer5.store import config
from chummer5.store.migrations import migrate

# Rows the list page shows, newest change first.
_ORDER = "ORDER BY updated DESC, id DESC"


class QuotaExceededError(Exception):
    """The owner already has as many characters as the quota allows."""


class RevisionConflictError(Exception):
    """The stored character changed since the caller loaded it (another device saved)."""


class UserExistsError(Exception):
    """A user with that name (compared case-insensitively) already exists."""


@dataclass(frozen=True)
class UserRecord:
    id: int
    username: str
    password_hash: str
    created: str
    last_login: str | None
    theme: str | None
    locale: str | None


@dataclass(frozen=True)
class CharacterSummary:
    """A character without its save: what the list page needs."""

    id: int
    owner_id: int
    display_name: str
    street_name: str
    metatype: str
    revision: int
    created: str
    updated: str


@dataclass(frozen=True)
class CharacterRecord(CharacterSummary):
    save_json: str


_SUMMARY_COLUMNS = "id, owner_id, display_name, street_name, metatype, revision, created, updated"


def now() -> str:
    """The timestamp format every column uses: UTC ISO-8601 with microseconds, which sorts
    lexically."""
    return datetime.now(UTC).isoformat(timespec="microseconds")


def names_from_save(save_json: str) -> tuple[str, str, str]:
    """(display name, street name, metatype) of a save, copied into columns on every write so
    listing and filtering never parse JSON. A save with no Bio yields empty names."""
    data = json.loads(save_json)
    bio = data.get("biography") or {}
    return (
        str(bio.get("name", "")),
        str(bio.get("street_name", "")),
        str(data.get("metatype_name", "")),
    )


def _like_pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class Store:
    def __init__(self, path: str | Path | None = None, *, quota: int | None = None) -> None:
        self.path = Path(path) if path is not None else config.database_path()
        self.quota = quota if quota is not None else config.character_quota()

    # -- connections --------------------------------------------------------------------------

    def initialize(self) -> None:
        """Create the file if needed and apply pending migrations. Call once at startup."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            migrate(db)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA foreign_keys = ON")
            yield db
        finally:
            db.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        """A connection inside `BEGIN IMMEDIATE`: committed on success, rolled back on error."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.execute("ROLLBACK")
                raise
            db.execute("COMMIT")

    # -- users --------------------------------------------------------------------------------

    def create_user(self, username: str, password_hash: str) -> UserRecord:
        with self._write() as db:
            try:
                cursor = db.execute(
                    "INSERT INTO users (username, password_hash, created) VALUES (?, ?, ?)",
                    (username, password_hash, now()),
                )
            except sqlite3.IntegrityError:
                raise UserExistsError(username) from None
            row = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return UserRecord(**dict(row))

    def get_user(self, user_id: int) -> UserRecord | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return UserRecord(**dict(row)) if row else None

    def get_user_by_name(self, username: str) -> UserRecord | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return UserRecord(**dict(row)) if row else None

    def delete_user(self, user_id: int) -> bool:
        """Delete a user; their characters and login sessions go with them (cascade)."""
        with self._write() as db:
            return db.execute("DELETE FROM users WHERE id = ?", (user_id,)).rowcount > 0

    # -- characters ---------------------------------------------------------------------------

    def count_characters(self, owner_id: int) -> int:
        with self._connect() as db:
            row = db.execute(
                "SELECT COUNT(*) FROM characters WHERE owner_id = ?", (owner_id,)
            ).fetchone()
        return int(row[0])

    def create_character(self, owner_id: int, save_json: str) -> CharacterRecord:
        """Insert a new character. Raises `QuotaExceededError` when the owner is at quota; the
        count and the insert share one write transaction, so concurrent inserts can't both pass."""
        display_name, street_name, metatype = names_from_save(save_json)
        stamp = now()
        with self._write() as db:
            count = db.execute(
                "SELECT COUNT(*) FROM characters WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]
            if count >= self.quota:
                raise QuotaExceededError(owner_id)
            cursor = db.execute(
                "INSERT INTO characters (owner_id, display_name, street_name, metatype, "
                "save_json, revision, created, updated) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (owner_id, display_name, street_name, metatype, save_json, stamp, stamp),
            )
            row = db.execute(
                "SELECT * FROM characters WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return CharacterRecord(**dict(row))

    def get_character(self, owner_id: int, character_id: int) -> CharacterRecord | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM characters WHERE id = ? AND owner_id = ?",
                (character_id, owner_id),
            ).fetchone()
        return CharacterRecord(**dict(row)) if row else None

    def list_characters(
        self, owner_id: int, name_filter: str | None = None
    ) -> list[CharacterSummary]:
        """The owner's characters, most recently changed first. `name_filter` matches a substring
        of the name or street name, in SQL. (SQLite's `LIKE` ignores case for ASCII only.)"""
        sql = f"SELECT {_SUMMARY_COLUMNS} FROM characters WHERE owner_id = ?"
        params: list[object] = [owner_id]
        if name_filter and name_filter.strip():
            sql += " AND (display_name LIKE ? ESCAPE '\\' OR street_name LIKE ? ESCAPE '\\')"
            pattern = _like_pattern(name_filter.strip())
            params += [pattern, pattern]
        with self._connect() as db:
            rows = db.execute(f"{sql} {_ORDER}", params).fetchall()
        return [CharacterSummary(**dict(row)) for row in rows]

    def update_character(
        self,
        owner_id: int,
        character_id: int,
        save_json: str,
        *,
        expected_revision: int | None = None,
    ) -> int | None:
        """Overwrite a character's save and return its new revision, or None if the owner has no
        such character. With `expected_revision`, the write happens only if the stored revision
        still matches (otherwise `RevisionConflictError`): WP138's cross-device check. Overwriting
        never counts against the quota."""
        display_name, street_name, metatype = names_from_save(save_json)
        sql = (
            "UPDATE characters SET display_name = ?, street_name = ?, metatype = ?, "
            "save_json = ?, revision = revision + 1, updated = ? WHERE id = ? AND owner_id = ?"
        )
        params: list[object] = [
            display_name,
            street_name,
            metatype,
            save_json,
            now(),
            character_id,
            owner_id,
        ]
        if expected_revision is not None:
            sql += " AND revision = ?"
            params.append(expected_revision)
        with self._write() as db:
            if db.execute(sql, params).rowcount == 0:
                exists = db.execute(
                    "SELECT 1 FROM characters WHERE id = ? AND owner_id = ?",
                    (character_id, owner_id),
                ).fetchone()
                if exists:
                    raise RevisionConflictError(character_id)
                return None
            row = db.execute(
                "SELECT revision FROM characters WHERE id = ?", (character_id,)
            ).fetchone()
        return int(row[0])

    def delete_character(self, owner_id: int, character_id: int) -> bool:
        with self._write() as db:
            return (
                db.execute(
                    "DELETE FROM characters WHERE id = ? AND owner_id = ?",
                    (character_id, owner_id),
                ).rowcount
                > 0
            )
