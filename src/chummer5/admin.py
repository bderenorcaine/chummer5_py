"""The admin CLI (WP137): `python -m chummer5.admin <command>`.

A thin `argparse` layer over `chummer5.accounts`, which holds the logic, so a later admin page can
reuse it. Every command is listed in `spec/admin-primer.md`; keep that file in step with this one.
The database is `CHUMMER5_DB`, the same one the server uses.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from typing import TextIO

from chummer5 import accounts
from chummer5.store import Store


def cmd_invite(store: Store, args: argparse.Namespace, out: TextIO) -> int:
    invite = accounts.mint_invite(store, expires_days=args.expires_days)
    print(accounts.format_invite(invite.code), file=out)
    if invite.expires:
        print(f"expires {invite.expires}", file=sys.stderr)
    return 0


def cmd_invites(store: Store, args: argparse.Namespace, out: TextIO) -> int:
    invites = store.list_open_invites()
    if not invites:
        print("no open invites", file=out)
    for invite in invites:
        expires = invite.expires or "never"
        print(
            f"{accounts.format_invite(invite.code)}  created {invite.created}  expires {expires}",
            file=out,
        )
    return 0


def cmd_revoke(store: Store, args: argparse.Namespace, out: TextIO) -> int:
    if accounts.revoke_invite(store, args.code):
        print("revoked", file=out)
        return 0
    print(f"no open invite {args.code!r}", file=sys.stderr)
    return 1


def cmd_users(store: Store, args: argparse.Namespace, out: TextIO) -> int:
    listings = store.list_users()
    if not listings:
        print("no users", file=out)
    for listing in listings:
        user = listing.user
        flags = "  (must change password)" if user.must_change_password else ""
        print(
            f"{user.username}  characters {listing.character_count}  created {user.created}  "
            f"last login {user.last_login or 'never'}{flags}",
            file=out,
        )
    return 0


def cmd_reset_password(store: Store, args: argparse.Namespace, out: TextIO) -> int:
    try:
        temporary = accounts.reset_password(store, args.username)
    except LookupError:
        print(f"no user {args.username!r}", file=sys.stderr)
        return 1
    print(temporary, file=out)
    print(
        "one-time password; the user must choose a new one at the next login, "
        "and every session they had has ended",
        file=sys.stderr,
    )
    return 0


def cmd_delete_user(store: Store, args: argparse.Namespace, out: TextIO) -> int:
    user = store.get_user_by_name(args.username)
    if user is None:
        print(f"no user {args.username!r}", file=sys.stderr)
        return 1
    if not args.yes:
        count = store.count_characters(user.id)
        print(
            f"This deletes {user.username} and their {count} character(s). It cannot be undone.",
            file=sys.stderr,
        )
        answer = input(f"Type {user.username} to confirm: ")
        if answer.strip() != user.username:
            print("not deleted", file=sys.stderr)
            return 1
    accounts.delete_user(store, user.username)
    print(f"deleted {user.username}", file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m chummer5.admin",
        description="Manage Chummer5 accounts and invites. Uses the database in CHUMMER5_DB.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    invite = commands.add_parser("invite", help="mint an invite code and print it")
    invite.add_argument(
        "--expires-days", type=float, metavar="N", help="the code stops working after N days"
    )
    invite.set_defaults(func=cmd_invite)

    commands.add_parser("invites", help="list open invite codes").set_defaults(func=cmd_invites)

    revoke = commands.add_parser("revoke", help="revoke an unused invite code")
    revoke.add_argument("code")
    revoke.set_defaults(func=cmd_revoke)

    commands.add_parser("users", help="list accounts").set_defaults(func=cmd_users)

    reset = commands.add_parser(
        "reset-password", help="print a one-time password for a user and end their sessions"
    )
    reset.add_argument("username")
    reset.set_defaults(func=cmd_reset_password)

    delete = commands.add_parser(
        "delete-user", help="delete a user, their characters and their sessions"
    )
    delete.add_argument("username")
    delete.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    delete.set_defaults(func=cmd_delete_user)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    store: Store | None = None,
    out: TextIO | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    command: Callable[[Store, argparse.Namespace, TextIO], int] = args.func
    return command(store or Store(), args, out or sys.stdout)


if __name__ == "__main__":
    sys.exit(main())
