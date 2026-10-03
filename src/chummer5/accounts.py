"""Accounts, invites and login sessions (WP137): the logic behind both the web pages and the
admin CLI, with no web imports, so a later admin page can call the same functions.

**Passwords** are hashed with stdlib `hashlib.scrypt`, a per-user random salt, and the parameters
stored in the hash string (`scrypt$<n>$<r>$<p>$<salt>$<key>`, base64), so the cost can be raised
later without invalidating old hashes. Comparison is `hmac.compare_digest`.

**Login sessions**: the cookie holds a random token; the database holds only its SHA-256. Looking a
session up by that hash is an ordinary indexed SQL equality, which is fine: an attacker who could
time it would learn bytes of a *hash* of a 256-bit random token, which gets them nothing.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from chummer5.store import (
    AuthSessionRecord,
    InviteInvalidError,
    InviteRecord,
    Store,
    UserExistsError,
    UserRecord,
    stamp,
)


class AccountError(Exception):
    """A request the player can fix. `key` is the i18n key of the message to show them."""

    def __init__(self, key: str, **params: object) -> None:
        super().__init__(key)
        self.key = key
        self.params = params


class ServerBusyError(AccountError):
    """Every password-hashing slot stayed taken for `HASH_WAIT_SECONDS`."""

    def __init__(self) -> None:
        super().__init__("Web_Auth_Busy")


# --- configuration -------------------------------------------------------------------------------

Mode = Literal["local", "hosted"]
LOCAL: Mode = "local"
HOSTED: Mode = "hosted"


def app_mode() -> Mode:
    """`CHUMMER5_MODE`: `local` (the default; no login, one implicit user) or `hosted`."""
    raw = os.environ.get("CHUMMER5_MODE", LOCAL).strip().lower() or LOCAL
    if raw == LOCAL:
        return LOCAL
    if raw == HOSTED:
        return HOSTED
    raise ValueError(f"CHUMMER5_MODE must be 'local' or 'hosted', got {raw!r}")


DEFAULT_SESSION_DAYS = 30
MAX_SESSION_DAYS = 3650
# How stale `last_seen` may get before a request slides the session's expiry forward. Bounds the
# database writes to one per session per interval, instead of one per request.
SESSION_REFRESH_INTERVAL = timedelta(minutes=5)


def session_lifetime() -> timedelta:
    """`CHUMMER5_SESSION_DAYS`, else 30: how long a login lasts without being used. Read per use,
    but `create_app` calls it once at startup in hosted mode, so a bad value stops the server
    from starting instead of failing every login."""
    raw = os.environ.get("CHUMMER5_SESSION_DAYS", "").strip()
    if not raw:
        return timedelta(days=DEFAULT_SESSION_DAYS)
    try:
        days = float(raw)
    except ValueError:
        raise ValueError(f"CHUMMER5_SESSION_DAYS must be a number of days, got {raw!r}") from None
    if not 0 < days <= MAX_SESSION_DAYS:  # also refuses nan and inf
        raise ValueError(
            f"CHUMMER5_SESSION_DAYS must be above 0 and at most {MAX_SESSION_DAYS}, got {raw!r}"
        )
    return timedelta(days=days)


# --- passwords -----------------------------------------------------------------------------------

MIN_PASSWORD_LENGTH = 10
# Not a strength rule: an upper bound on what is fed to scrypt per attempt.
MAX_PASSWORD_LENGTH = 1024


@dataclass(frozen=True)
class ScryptParams:
    n: int
    r: int
    p: int

    @property
    def maxmem(self) -> int:
        # scrypt needs 128 * r * n bytes; hashlib refuses anything above `maxmem` (default 32 MiB).
        return 128 * self.r * self.n * 2


# OWASP's recommended minimum for scrypt: about 0.3 s and 128 MiB per hash on the dev machine.
# Tests lower this module attribute; stored hashes carry their own parameters regardless.
SCRYPT_PARAMS = ScryptParams(n=2**17, r=8, p=1)
_SALT_BYTES = 16
_KEY_BYTES = 32


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


# At most this many hashes run at once, process-wide. Each one holds 128 MiB for about 0.3 s, and
# the login/register handlers run in a thread pool of about 40: unbounded, 40 concurrent anonymous
# POSTs would want 5 GiB. Two slots cap it at 256 MiB, and still hash about six logins a second. A
# request that can't get a slot within `HASH_WAIT_SECONDS` is turned away with `ServerBusyError`
# rather than holding a pool thread (which chargen GETs also need) indefinitely.
MAX_CONCURRENT_HASHES = 2
HASH_WAIT_SECONDS = 10.0
_hash_slots = threading.BoundedSemaphore(MAX_CONCURRENT_HASHES)


def _scrypt(password: str, salt: bytes, params: ScryptParams) -> bytes:
    if not _hash_slots.acquire(timeout=HASH_WAIT_SECONDS):
        raise ServerBusyError()
    try:
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=params.n,
            r=params.r,
            p=params.p,
            maxmem=params.maxmem,
            dklen=_KEY_BYTES,
        )
    finally:
        _hash_slots.release()


def hash_password(password: str) -> str:
    params = SCRYPT_PARAMS
    salt = secrets.token_bytes(_SALT_BYTES)
    key = _scrypt(password, salt, params)
    return f"scrypt${params.n}${params.r}${params.p}${_b64(salt)}${_b64(key)}"


def is_usable_hash(stored: str) -> bool:
    """False for the local user's `!`, or anything else not a scrypt hash: nothing opens it."""
    return stored.startswith("scrypt$")


def verify_password(password: str, stored: str) -> bool:
    """True if `password` matches `stored`. A malformed or unusable hash (the local user's `!`)
    never matches."""
    try:
        scheme, n, r, p, salt, key = stored.split("$")
        if scheme != "scrypt":
            return False
        params = ScryptParams(int(n), int(r), int(p))
        expected = base64.b64decode(key)
        actual = _scrypt(password, base64.b64decode(salt), params)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# A hash nothing matches, verified against when the username is unknown, so that a wrong username
# costs the same scrypt as a wrong password and response time doesn't reveal which accounts exist.
_dummy_hash: str | None = None


def _burn_password_check(password: str) -> None:
    global _dummy_hash
    if _dummy_hash is None or not _dummy_hash.startswith(f"scrypt${SCRYPT_PARAMS.n}$"):
        _dummy_hash = hash_password(secrets.token_urlsafe(16))
    verify_password(password, _dummy_hash)


# --- usernames -----------------------------------------------------------------------------------

MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 32
_USERNAME = re.compile(r"[A-Za-z0-9_.-]+")


# Local mode's implicit user. Reserved, so no hosted account can take the name: the same database
# opened in local mode would otherwise hand that person's account (and characters) to whoever runs
# it locally.
LOCAL_USERNAME = "local"
RESERVED_USERNAMES = frozenset({LOCAL_USERNAME})


def check_username(username: str) -> str:
    username = username.strip()
    if not MIN_USERNAME_LENGTH <= len(username) <= MAX_USERNAME_LENGTH:
        raise AccountError(
            "Web_Auth_UsernameLength", min=MIN_USERNAME_LENGTH, max=MAX_USERNAME_LENGTH
        )
    if not _USERNAME.fullmatch(username):
        raise AccountError("Web_Auth_UsernameChars")
    if username.lower() in RESERVED_USERNAMES:
        raise AccountError("Web_Auth_UsernameTaken")
    return username


def check_new_password(password: str, confirm: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AccountError("Web_Auth_PasswordTooShort", min=MIN_PASSWORD_LENGTH)
    if len(password) > MAX_PASSWORD_LENGTH:
        raise AccountError("Web_Auth_PasswordTooLong", max=MAX_PASSWORD_LENGTH)
    if password != confirm:
        raise AccountError("Web_Auth_PasswordMismatch")


# --- invites -------------------------------------------------------------------------------------

# Crockford-style base32 without I, L, O, U: nothing to misread when a code is typed off a chat
# message. 16 characters is 80 bits.
_INVITE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_INVITE_LENGTH = 16
_INVITE_GROUP = 4


def format_invite(code: str) -> str:
    """`ABCDEFGH...` as `ABCD-EFGH-...`, the way it is printed and handed out."""
    return "-".join(code[i : i + _INVITE_GROUP] for i in range(0, len(code), _INVITE_GROUP))


def normalize_invite(text: str) -> str:
    """What a player typed, as stored: upper-case, without dashes or spaces."""
    return re.sub(r"[\s-]", "", text).upper()


def mint_invite(store: Store, *, expires_days: float | None = None) -> InviteRecord:
    code = "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(_INVITE_LENGTH))
    expires = None
    if expires_days is not None:
        if expires_days <= 0:
            raise ValueError("expires_days must be positive")
        expires = stamp(datetime.now(UTC) + timedelta(days=expires_days))
    return store.create_invite(code, expires)


def revoke_invite(store: Store, code: str) -> bool:
    return store.revoke_invite(normalize_invite(code))


# --- sessions ------------------------------------------------------------------------------------


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LoginSession:
    """A freshly issued login: `token` goes into the cookie and is never stored."""

    token: str
    user: UserRecord

    @property
    def token_hash(self) -> str:
        return hash_token(self.token)


def start_session(store: Store, user: UserRecord, *, record_login: bool = True) -> LoginSession:
    """Issue a brand-new token for `user` (never reusing one). A login also stamps `last_login`;
    a password change, which starts a session without being a login, passes `record_login=False`.
    """
    token = secrets.token_urlsafe(32)
    expires = stamp(datetime.now(UTC) + session_lifetime())
    store.create_auth_session(hash_token(token), user.id, expires, record_login=record_login)
    return LoginSession(token, user)


@dataclass(frozen=True)
class ResolvedSession:
    record: AuthSessionRecord
    user: UserRecord
    # True when this lookup slid the expiry forward, so the cookie should be re-sent too.
    refreshed: bool


def resolve_session(store: Store, token: str) -> ResolvedSession | None:
    """The live session behind a cookie token, sliding its expiry if it was last seen more than
    `SESSION_REFRESH_INTERVAL` ago. None if the token is unknown or expired."""
    token_hash = hash_token(token)
    found = store.get_auth_session(token_hash)
    if found is None:
        return None
    record, user = found
    now = datetime.now(UTC)
    if now - datetime.fromisoformat(record.last_seen) < SESSION_REFRESH_INTERVAL:
        return ResolvedSession(record, user, refreshed=False)
    store.touch_auth_session(token_hash, stamp(now + session_lifetime()))
    return ResolvedSession(record, user, refreshed=True)


def end_session(store: Store, token: str) -> None:
    store.delete_auth_session(hash_token(token))


# --- account operations --------------------------------------------------------------------------


def register(
    store: Store, username: str, password: str, confirm: str, invite_code: str
) -> UserRecord:
    """Create an account with an invite. Raises `AccountError` with the message to show.

    The invite is checked before anything else costly, so that without a valid code no request can
    make the server hash a password; and before the username, so that without one nobody can probe
    which names exist. Both checks are repeated atomically by `register_user`."""
    username = check_username(username)
    check_new_password(password, confirm)
    code = normalize_invite(invite_code)
    if not store.invite_is_open(code):
        raise AccountError("Web_Auth_InviteInvalid")
    if store.get_user_by_name(username) is not None:
        raise AccountError("Web_Auth_UsernameTaken")
    password_hash = hash_password(password)
    try:
        return store.register_user(username, password_hash, code)
    except InviteInvalidError:
        raise AccountError("Web_Auth_InviteInvalid") from None
    except UserExistsError:
        raise AccountError("Web_Auth_UsernameTaken") from None


def authenticate(store: Store, username: str, password: str) -> UserRecord:
    """The user with these credentials, or `AccountError` -- the same one for an unknown user and
    a wrong password, after the same amount of work."""
    if len(password) > MAX_PASSWORD_LENGTH:
        raise AccountError("Web_Auth_LoginFailed")
    user = store.get_user_by_name(username.strip())
    # An account no password opens (the local user's `!`) is checked like a missing one: rejecting
    # it without a hash would answer faster, and so tell that the account exists.
    if user is None or not is_usable_hash(user.password_hash):
        _burn_password_check(password)
        raise AccountError("Web_Auth_LoginFailed")
    if not verify_password(password, user.password_hash):
        raise AccountError("Web_Auth_LoginFailed")
    return user


def change_password(
    store: Store, user: UserRecord, current: str, new: str, confirm: str
) -> LoginSession:
    """A player's own password change. Ends every session the user has, including the current
    one, and returns a fresh session for the caller to continue in."""
    if not verify_password(current, user.password_hash):
        raise AccountError("Web_Auth_CurrentPasswordWrong")
    check_new_password(new, confirm)
    if new == current:
        raise AccountError("Web_Auth_PasswordUnchanged")
    store.set_password(user.id, hash_password(new))
    refreshed = store.get_user(user.id)
    assert refreshed is not None
    return start_session(store, refreshed, record_login=False)


def reset_password(store: Store, username: str) -> str:
    """Admin: give `username` a one-time password, returned for the admin to hand over. The player
    must replace it at their next login. Every session the user had ends (a reset is often
    because one was stolen). Raises `LookupError` for an unknown user."""
    user = store.get_user_by_name(username)
    if user is None:
        raise LookupError(username)
    temporary = secrets.token_urlsafe(12)  # 16 characters, above MIN_PASSWORD_LENGTH
    store.set_password(user.id, hash_password(temporary), must_change_password=True)
    return temporary


def delete_user(store: Store, username: str) -> UserRecord:
    """Admin: delete `username`, their characters and their sessions. Raises `LookupError`."""
    user = store.get_user_by_name(username)
    if user is None:
        raise LookupError(username)
    store.delete_user(user.id)
    return user


# --- local mode ----------------------------------------------------------------------------------

# Not a scrypt hash, so `verify_password` never matches it: nobody can log in as the local user.
UNUSABLE_PASSWORD_HASH = "!"


def ensure_local_user(store: Store) -> UserRecord:
    """Local mode's one implicit user, created the first time it is asked for. Refuses to adopt a
    real account of that name (one with a usable password, from before the name was reserved)."""
    user = store.get_user_by_name(LOCAL_USERNAME)
    if user is not None:
        if is_usable_hash(user.password_hash):
            raise RuntimeError(
                f"the database has a real account named {LOCAL_USERNAME!r}; rename or delete it "
                "before running in local mode"
            )
        return user
    try:
        return store.create_user(LOCAL_USERNAME, UNUSABLE_PASSWORD_HASH)
    except UserExistsError:  # created concurrently
        found = store.get_user_by_name(LOCAL_USERNAME)
        assert found is not None
        return found
