"""Persistence for the hosted deployment (WP136): users, invites, login sessions, characters.

Stdlib `sqlite3` only. Everything outside this package goes through `Store`; no route writes SQL.
"""

from chummer5.store.repository import (
    AuthSessionRecord,
    CharacterRecord,
    CharacterSummary,
    InviteInvalidError,
    InviteRecord,
    QuotaExceededError,
    RevisionConflictError,
    Store,
    UserExistsError,
    UserListing,
    UserRecord,
    stamp,
)

__all__ = [
    "AuthSessionRecord",
    "CharacterRecord",
    "CharacterSummary",
    "InviteInvalidError",
    "InviteRecord",
    "QuotaExceededError",
    "RevisionConflictError",
    "Store",
    "UserExistsError",
    "UserListing",
    "UserRecord",
    "stamp",
]
