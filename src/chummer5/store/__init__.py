"""Persistence for the hosted deployment (WP136): users, invites, login sessions, characters.

Stdlib `sqlite3` only. Everything outside this package goes through `Store`; no route writes SQL.
"""

from chummer5.store.repository import (
    CharacterRecord,
    CharacterSummary,
    QuotaExceededError,
    RevisionConflictError,
    Store,
    UserExistsError,
    UserRecord,
)

__all__ = [
    "CharacterRecord",
    "CharacterSummary",
    "QuotaExceededError",
    "RevisionConflictError",
    "Store",
    "UserExistsError",
    "UserRecord",
]
