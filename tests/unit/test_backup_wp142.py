"""WP142: taking a backup of the live database (online, consistent) and restoring one."""

from __future__ import annotations

import io
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from chummer5 import accounts, admin
from chummer5.store import Store
from chummer5.store.backup import BackupError, backup, backups, restore
from chummer5.store.migrations import MIGRATIONS, current_version

SAVE = json.dumps({"biography": {"name": "Backed Up"}, "metatype_name": "Human"})


@pytest.fixture(autouse=True)
def _cheap_scrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(accounts, "SCRYPT_PARAMS", accounts.ScryptParams(n=2**4, r=8, p=1))
    monkeypatch.setattr(accounts, "_dummy_hash", None)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "live" / "chummer5.db")


def populate(store: Store, username: str = "alice", characters: int = 2) -> int:
    user = store.create_user(username, accounts.hash_password("a long password"))
    for _ in range(characters):
        store.create_character(user.id, SAVE)
    return user.id


def test_a_backup_is_one_sound_file_with_the_data(store: Store, tmp_path: Path) -> None:
    owner = populate(store)
    path = backup(store, tmp_path / "backups", now=datetime(2026, 10, 3, 12, 0, 1, tzinfo=UTC))
    assert path.name == "chummer5-20261003-120001.db"
    assert not path.with_name(path.name + "-wal").exists()
    assert not list(path.parent.glob("*.partial"))
    with sqlite3.connect(path) as db:  # before Store opens it, which switches it to WAL
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert Store(path).count_characters(owner) == 2


def test_backup_is_consistent_while_the_server_writes(store: Store, tmp_path: Path) -> None:
    owner = populate(store, characters=0)
    stop = threading.Event()

    def writer() -> None:
        while not stop.is_set():
            store.create_character(owner, SAVE)

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        taken = [backup(store, tmp_path / "backups") for _ in range(5)]
    finally:
        stop.set()
        thread.join()
    counts = [Store(path).count_characters(owner) for path in taken]
    assert counts == sorted(counts)  # each a snapshot, later ones no smaller
    assert store.count_characters(owner) >= counts[-1]
    for path in taken:
        with sqlite3.connect(path) as db:
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_keep_prunes_to_the_newest(store: Store, tmp_path: Path) -> None:
    directory = tmp_path / "backups"
    (directory / "unrelated.db").parent.mkdir(parents=True)
    (directory / "unrelated.db").write_text("mine")
    for second in range(5):
        backup(store, directory, keep=3, now=datetime(2026, 10, 3, 12, 0, second, tzinfo=UTC))
    names = [p.name for p in backups(directory)]
    assert names == [f"chummer5-20261003-12000{s}.db" for s in (2, 3, 4)]
    assert (directory / "unrelated.db").exists()  # only its own files are pruned


def test_two_backups_in_one_second_do_not_collide(store: Store, tmp_path: Path) -> None:
    moment = datetime(2026, 10, 3, 12, 0, 0, tzinfo=UTC)
    first = backup(store, tmp_path, now=moment)
    second = backup(store, tmp_path, now=moment)
    assert first != second and second.name == "chummer5-20261003-120000-1.db"


def test_restore_brings_back_exactly_the_backup(store: Store, tmp_path: Path) -> None:
    alice = populate(store, "alice")
    saved = backup(store, tmp_path / "backups")
    store.delete_user(alice)
    populate(store, "mallory")
    assert restore(store, saved) == len(MIGRATIONS)
    fresh = Store(store.path)
    assert [u.user.username for u in fresh.list_users()] == ["alice"]
    assert fresh.count_characters(alice) == 2
    fresh.create_character(alice, SAVE)  # and it is writable, WAL and all
    assert fresh.count_characters(alice) == 3


def test_restoring_an_older_schema_migrates_on_next_use(store: Store, tmp_path: Path) -> None:
    old = tmp_path / "old.db"
    with sqlite3.connect(old, isolation_level=None) as db:
        MIGRATIONS[0](db)
        db.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        db.execute("INSERT INTO schema_version VALUES (1)")
    assert restore(store, old) == 1
    Store(store.path).list_users()  # triggers the migration
    with sqlite3.connect(store.path) as db:
        assert current_version(db) == len(MIGRATIONS)


def test_restore_refuses_what_it_cannot_trust(store: Store, tmp_path: Path) -> None:
    populate(store)
    garbage = tmp_path / "garbage.db"
    garbage.write_bytes(b"not a database at all" * 100)
    with pytest.raises(BackupError, match="not an SQLite database"):
        restore(store, garbage)
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    with pytest.raises(BackupError, match="not a Chummer5 database"):
        restore(store, empty)
    future = backup(store, tmp_path / "b")
    with sqlite3.connect(future) as db:
        db.execute("UPDATE schema_version SET version = 99")
    with pytest.raises(BackupError, match="newer than this program knows"):
        restore(store, future)
    with pytest.raises(BackupError, match="no such file"):
        restore(store, tmp_path / "missing.db")
    assert Store(store.path).list_users()[0].user.username == "alice"  # live data untouched


def run(store: Store, *argv: str) -> tuple[int, str]:
    out = io.StringIO()
    return admin.main(list(argv), store=store, out=out), out.getvalue()


def test_admin_backup_and_restore(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    populate(store)
    code, printed = run(store, "backup", "--keep", "2")
    assert code == 0
    path = Path(printed.strip())
    assert path.parent == store.path.parent / "backups" and path.exists()

    populate(store, "mallory")
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    assert run(store, "restore", str(path))[0] == 1  # not confirmed
    assert len(Store(store.path).list_users()) == 2
    monkeypatch.setattr("builtins.input", lambda prompt: "restore")
    code, printed = run(store, "restore", str(path))
    assert code == 0 and "restored" in printed
    assert [u.user.username for u in Store(store.path).list_users()] == ["alice"]
    assert run(store, "restore", "--yes", str(tmp_path / "nope.db"))[0] == 1
