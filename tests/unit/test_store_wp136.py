"""WP136: the SQLite storage layer -- CRUD, owner scoping, quota, revisions, migrations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from chummer5.store import (
    QuotaExceededError,
    RevisionConflictError,
    Store,
    UserExistsError,
)
from chummer5.store import config as store_config
from chummer5.store.migrations import MIGRATIONS, migrate


def save(name: str = "", street: str = "", metatype: str = "Human", **extra: object) -> str:
    bio = {k: v for k, v in (("name", name), ("street_name", street)) if v}
    return json.dumps({"format_version": 2, "metatype_name": metatype, "biography": bio, **extra})


@pytest.fixture
def store(tmp_path: Path) -> Store:
    s = Store(tmp_path / "test.db", quota=100)
    s.initialize()
    return s


@pytest.fixture
def alice(store: Store) -> int:
    return store.create_user("Alice", "hash").id


@pytest.fixture
def bob(store: Store) -> int:
    return store.create_user("Bob", "hash").id


def test_initialize_from_empty_file_applies_every_migration(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    path.touch()
    Store(path).initialize()
    db = sqlite3.connect(path)
    assert db.execute("SELECT version FROM schema_version").fetchone() == (len(MIGRATIONS),)
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"users", "invite_codes", "auth_sessions", "characters", "schema_version"} <= tables
    assert db.execute("PRAGMA journal_mode").fetchone() == ("wal",)


def test_migrate_is_idempotent(store: Store) -> None:
    store.create_user("keep", "h")
    store.initialize()
    assert store.get_user_by_name("keep") is not None


def test_migrations_run_in_order_and_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    extra = [lambda db: calls.append(2), lambda db: calls.append(3)]
    path = tmp_path / "m.db"
    db = sqlite3.connect(path, isolation_level=None)
    migrate(db)
    monkeypatch.setattr("chummer5.store.migrations.MIGRATIONS", MIGRATIONS + extra)
    migrate(db)
    migrate(db)
    assert calls == [2, 3]
    assert db.execute("SELECT version FROM schema_version").fetchone() == (len(MIGRATIONS) + 2,)


def test_failed_migration_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(db: sqlite3.Connection) -> None:
        db.execute("CREATE TABLE half (x)")
        raise RuntimeError("boom")

    db = sqlite3.connect(tmp_path / "m.db", isolation_level=None)
    migrate(db)
    monkeypatch.setattr("chummer5.store.migrations.MIGRATIONS", MIGRATIONS + [broken])
    with pytest.raises(RuntimeError):
        migrate(db)
    assert db.execute("SELECT version FROM schema_version").fetchone() == (len(MIGRATIONS),)
    assert db.execute("SELECT 1 FROM sqlite_master WHERE name = 'half'").fetchone() is None


def test_newer_schema_is_refused(tmp_path: Path) -> None:
    db = sqlite3.connect(tmp_path / "n.db", isolation_level=None)
    migrate(db)
    db.execute("UPDATE schema_version SET version = 999")
    with pytest.raises(RuntimeError, match="newer"):
        migrate(db)


def test_character_round_trip(store: Store, alice: int) -> None:
    created = store.create_character(alice, save("Ali", "Alias", "Elf"))
    assert (created.display_name, created.street_name, created.metatype) == ("Ali", "Alias", "Elf")
    assert created.revision == 1
    got = store.get_character(alice, created.id)
    assert got == created

    new_save = save("Ali", "Renamed", "Elf", extra_key=1)
    assert store.update_character(alice, created.id, new_save) == 2
    got = store.get_character(alice, created.id)
    assert got is not None
    assert got.save_json == new_save  # stored verbatim
    assert got.street_name == "Renamed"  # names re-copied on every write
    assert got.revision == 2
    assert got.updated >= got.created

    assert store.delete_character(alice, created.id) is True
    assert store.get_character(alice, created.id) is None
    assert store.delete_character(alice, created.id) is False


def test_save_without_bio_has_empty_names(store: Store, alice: int) -> None:
    rec = store.create_character(alice, json.dumps({"metatype_name": "Troll"}))
    assert (rec.display_name, rec.street_name, rec.metatype) == ("", "", "Troll")


def test_owner_scoping(store: Store, alice: int, bob: int) -> None:
    rec = store.create_character(alice, save("Secret"))
    assert store.get_character(bob, rec.id) is None
    assert store.update_character(bob, rec.id, save("Hijacked")) is None
    assert store.update_character(bob, rec.id, save("Hijacked"), expected_revision=1) is None
    assert store.delete_character(bob, rec.id) is False
    assert store.list_characters(bob) == []
    mine = store.get_character(alice, rec.id)
    assert mine is not None and mine.display_name == "Secret" and mine.revision == 1


def test_quota_boundary(tmp_path: Path) -> None:
    store = Store(tmp_path / "q.db", quota=100)
    store.initialize()
    uid = store.create_user("u", "h").id
    first = store.create_character(uid, save("c0"))
    for i in range(1, 100):
        store.create_character(uid, save(f"c{i}"))  # the 100th insert succeeds
    assert store.count_characters(uid) == 100
    with pytest.raises(QuotaExceededError):
        store.create_character(uid, save("c100"))
    assert store.count_characters(uid) == 100
    # overwriting at quota is fine
    assert store.update_character(uid, first.id, save("rewritten")) == 2
    # quota is per user
    other = store.create_user("v", "h").id
    store.create_character(other, save("fine"))
    # freeing a slot allows another insert
    store.delete_character(uid, first.id)
    store.create_character(uid, save("again"))


def test_quota_is_configurable_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHUMMER5_CHARACTER_QUOTA", raising=False)
    assert store_config.character_quota() == 100
    monkeypatch.setenv("CHUMMER5_CHARACTER_QUOTA", "3")
    assert store_config.character_quota() == 3
    monkeypatch.setenv("CHUMMER5_CHARACTER_QUOTA", "many")
    with pytest.raises(ValueError):
        store_config.character_quota()


def test_database_path_from_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHUMMER5_DB", str(tmp_path / "x.db"))
    assert Store().path == tmp_path / "x.db"


def test_revision_check(store: Store, alice: int) -> None:
    rec = store.create_character(alice, save("A"))
    assert store.update_character(alice, rec.id, save("A1"), expected_revision=1) == 2
    with pytest.raises(RevisionConflictError):
        store.update_character(alice, rec.id, save("stale"), expected_revision=1)
    got = store.get_character(alice, rec.id)
    assert got is not None and got.display_name == "A1" and got.revision == 2


def test_list_sorted_newest_first_and_filtered(store: Store, alice: int, bob: int) -> None:
    a = store.create_character(alice, save("Alice Smith", "Alias"))
    b = store.create_character(alice, save("Bob", "Chrome"))
    c = store.create_character(alice, save("Cara", "ALIgator"))
    store.create_character(bob, save("Aliyah"))
    assert [r.id for r in store.list_characters(alice)] == [c.id, b.id, a.id]
    store.update_character(alice, a.id, save("Alice Smith", "Alias"))
    assert [r.id for r in store.list_characters(alice)][0] == a.id
    # matches name or street name, case-insensitively, only this owner's rows
    assert {r.id for r in store.list_characters(alice, "ali")} == {a.id, c.id}
    assert {r.id for r in store.list_characters(alice, "  CHROME ")} == {b.id}
    assert store.list_characters(alice, "zzz") == []
    assert len(store.list_characters(alice, "   ")) == 3


def test_filter_treats_wildcards_literally(store: Store, alice: int) -> None:
    store.create_character(alice, save("100% Human"))
    store.create_character(alice, save("a_b"))
    store.create_character(alice, save("axb"))
    assert len(store.list_characters(alice, "%")) == 1
    assert [r.display_name for r in store.list_characters(alice, "a_b")] == ["a_b"]


def test_usernames_are_unique_case_insensitively(store: Store) -> None:
    store.create_user("Dana", "h")
    with pytest.raises(UserExistsError):
        store.create_user("dANA", "h")
    found = store.get_user_by_name("DANA")
    assert found is not None and found.username == "Dana"


def test_delete_user_removes_their_characters(store: Store, alice: int, bob: int) -> None:
    rec = store.create_character(alice, save("Gone"))
    keep = store.create_character(bob, save("Kept"))
    assert store.delete_user(alice) is True
    assert store.get_user(alice) is None
    assert store.get_character(alice, rec.id) is None
    assert store.get_character(bob, keep.id) is not None


def test_foreign_keys_enforced(store: Store) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        store.create_character(9999, save("orphan"))
