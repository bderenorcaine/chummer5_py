"""WP140: downloading a stored character, and uploading JSON saves or legacy `.chum5` files as new
characters -- detection by content, the per-file quota, the size and count limits, and the
`defusedxml` hardening."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import Headers
from tests.fixtures.mundane_chum5 import (
    LEGACY_TESTFILES_DIR,
    PRIORITY_BUILD_FIXTURE,
    mundane_fixture_path,
)
from tests.unit.test_open_character_wp138 import confirm, logged_in, shell_token, user_id

from chummer5 import accounts
from chummer5.io.legacy_import import UnsupportedLegacyCharacterError, import_chum5
from chummer5.store import Store
from chummer5.web import uploads
from chummer5.web.app import create_app
from chummer5.web.catalogs import (
    BIOWARE,
    CYBERWARE_ENTRIES,
    LIFESTYLES,
    METATYPES,
    POWERS,
    PRIORITIES,
    QUALITIES,
    SKILLS,
    SPELLS,
    TRADITIONS,
)
from chummer5.web.routes.characters import download_filename

HTMX = {"HX-Request": "true"}
UPLOAD = "/characters/upload"
YETI = mundane_fixture_path(PRIORITY_BUILD_FIXTURE).read_bytes()

ENTITY_BOMB = b"""<?xml version="1.0"?>
<!DOCTYPE character [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>
<character><name>&b;</name></character>"""
EXTERNAL_ENTITY = b"""<?xml version="1.0"?>
<!DOCTYPE character [<!ENTITY secret SYSTEM "file:///etc/passwd">]>
<character><name>&secret;</name></character>"""


@pytest.fixture(autouse=True)
def _cheap_scrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(accounts, "SCRYPT_PARAMS", accounts.ScryptParams(n=2**4, r=8, p=1))
    monkeypatch.setattr(accounts, "_dummy_hash", None)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "wp140.db", quota=100)


@pytest.fixture
def local(store: Store) -> Iterator[TestClient]:
    with TestClient(create_app(mode="local", store=store), follow_redirects=False) as c:
        yield c


def owner(store: Store) -> int:
    return accounts.ensure_local_user(store).id


def make(client: TestClient, name: str = "", street: str = "") -> int:
    client.post("/characters/new")
    character_id = int(shell_token(confirm(client).text))
    if name or street:
        client.post("/ui/bio", data={"name": name, "street_name": street})
    return character_id


def upload(client: TestClient, *files: tuple[str, bytes], open_it: bool = False):  # type: ignore[no-untyped-def]
    url = f"{UPLOAD}?open=true" if open_it else UPLOAD
    parts = [("files", (name, data, "application/octet-stream")) for name, data in files]
    return client.post(url, files=parts, headers=HTMX)


def results(html: str) -> list[str]:
    """The list's per-file result lines, tags stripped."""
    items = re.findall(r'<li class="(info|error)">(.*?)</li>', html, re.S)
    return [f"{cls}: {' '.join(re.sub(r'<[^>]+>', '', text).split())}" for cls, text in items]


def count(store: Store) -> int:
    return store.count_characters(owner(store))


# --- download ------------------------------------------------------------------------------------


def test_download_is_the_stored_json_verbatim(local: TestClient, store: Store) -> None:
    character_id = make(local, "Jane Doe", "Ghost Wire")
    response = local.get(f"/characters/{character_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-disposition"] == 'attachment; filename="Ghost_Wire.json"'
    record = store.get_character(owner(store), character_id)
    assert record is not None and response.text == record.save_json


def test_download_and_upload_round_trip_to_an_equal_save(local: TestClient, store: Store) -> None:
    original = make(local, "Round Trip")
    downloaded = local.get(f"/characters/{original}/download").content
    response = upload(local, ("trip.json", downloaded))
    assert results(response.text) == ["info: trip.json: Character loaded."]
    [copy] = [s.id for s in store.list_characters(owner(store)) if s.id != original]
    again = local.get(f"/characters/{copy}/download").content
    assert json.loads(again) == json.loads(downloaded)


def test_download_is_owner_scoped(tmp_path: Path) -> None:
    store = Store(tmp_path / "hosted.db")
    app = create_app(mode="hosted", store=store)
    alice = logged_in(app, store, "alice")
    character_id = int(shell_token(confirm(alice).text))
    bob = logged_in(app, store, "bob")
    assert bob.get(f"/characters/{character_id}/download").status_code == 404
    assert alice.get(f"/characters/{character_id}/download").status_code == 200
    assert user_id(store, "alice") != user_id(store, "bob")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Ghost Wire", "Ghost_Wire.json"),
        ('Jäger / "Hunter"', "J_ger_Hunter.json"),
        ("../../etc/passwd", "etc_passwd.json"),
        ("", "character.json"),
        ("ーー", "character.json"),
        ("a-b_c", "a-b_c.json"),
    ],
)
def test_download_filename_is_sanitized(name: str, expected: str) -> None:
    assert download_filename(name) == expected


def test_export_page_downloads_the_stored_character(local: TestClient) -> None:
    character_id = make(local, "Exported")
    assert f'href="/characters/{character_id}/download"' in local.get("/ui/page/export").text


def test_list_rows_offer_download(local: TestClient) -> None:
    character_id = make(local, "Listed")
    assert f'href="/characters/{character_id}/download"' in local.get("/characters").text


# --- upload: detection, results, opening ---------------------------------------------------------


def test_list_upload_stores_each_file_and_opens_none(local: TestClient, store: Store) -> None:
    current = make(local, "Current")
    saved = local.get(f"/characters/{current}/download").content
    response = upload(local, ("a.json", saved), ("Yeti.chum5", YETI), ("junk.json", b"[]"))
    lines = results(response.text)
    assert lines[0] == "info: a.json: Character loaded."
    assert lines[1].startswith("info: Yeti.chum5: Character imported.")
    assert lines[2].startswith("error: junk.json: Could not load save")
    assert count(store) == 3  # the open one plus two uploads
    assert "Yeti-#ffffff" in response.text  # the new row is listed
    assert shell_token(local.get("/").text) == str(current)  # still the open one


def test_list_upload_carries_no_switch_warning(local: TestClient) -> None:
    make(local, "Current")
    page = local.get("/characters").text
    form = re.search(r'<form[^>]*hx-post="/characters/upload"[^>]*>', page)
    assert form and "hx-confirm" not in form.group(0)


def test_export_upload_opens_the_stored_character(local: TestClient, store: Store) -> None:
    first = make(local, "First")
    response = upload(local, ("Yeti.chum5", YETI), open_it=True)
    assert response.headers["HX-Retarget"] == "#app-shell"
    opened = shell_token(response.text)
    assert opened != str(first)
    assert "Character imported." in response.text
    assert store.get_character(owner(store), first) is not None  # left as it was


def test_export_upload_failure_keeps_the_open_character(local: TestClient) -> None:
    first = make(local, "First")
    response = upload(local, ("bad.json", b"not json"), open_it=True)
    assert "HX-Retarget" not in response.headers
    assert "Could not load save" in response.text
    assert shell_token(local.get("/").text) == str(first)


def test_content_decides_the_format_not_the_name(local: TestClient, store: Store) -> None:
    saved = local.get(f"/characters/{make(local)}/download").content
    response = upload(local, ("looks-like.chum5", saved), ("looks-like.json", YETI))
    lines = results(response.text)
    assert lines[0] == "info: looks-like.chum5: Character loaded."
    assert lines[1].startswith("info: looks-like.json: Character imported.")


def test_a_named_chum5_that_is_neither_reports_a_bad_chum5(local: TestClient) -> None:
    lines = results(upload(local, ("bad.chum5", b"this is not xml")).text)
    assert lines[0].startswith("error: bad.chum5: Not a valid .chum5 file")


def test_well_formed_xml_that_is_not_a_save_is_a_message(local: TestClient) -> None:
    junk = b"<character><contactpoints>many</contactpoints></character>"
    response = upload(local, ("odd.chum5", junk))
    assert response.status_code == 200
    assert results(response.text)[0].startswith("error: odd.chum5: Cannot import")


def test_no_file_chosen(local: TestClient) -> None:
    response = local.post(UPLOAD, files=[("files", ("", b"", "application/octet-stream"))])
    assert results(response.text) == ["error: Choose a JSON save or a .chum5 file to upload."]
    assert "Choose a JSON save" in local.post(UPLOAD, data={"q": ""}).text


def test_upload_keeps_the_list_filter(local: TestClient) -> None:
    make(local, "Alias")
    make(local, "Bob")
    response = local.post(
        UPLOAD,
        data={"q": "ali"},
        files=[("files", ("Yeti.chum5", YETI, "application/octet-stream"))],
    )
    assert "Alias" in response.text and ">Bob" not in response.text


def test_every_chum5_fixture_imports_through_the_upload_route(local: TestClient) -> None:
    """Every legacy test file (the `tests/fixtures` registry draws on these) comes out of the
    upload route as out of a direct import: imported if that succeeds, "Cannot import" if not --
    never refused as unsafe XML, never a 500."""
    paths = sorted(LEGACY_TESTFILES_DIR.glob("*.chum5"))
    assert len(paths) >= 30
    expected = {}
    for path in paths:
        try:
            import_chum5(
                path,
                metatypes=METATYPES,
                priorities=PRIORITIES,
                skills=SKILLS,
                qualities=QUALITIES,
                lifestyles=LIFESTYLES,
                traditions=TRADITIONS,
                spells=SPELLS,
                powers=POWERS,
                cyberware=CYBERWARE_ENTRIES,
                bioware=BIOWARE,
            )
            expected[path.name] = True
        # A plain ValueError: two files the importer can't take (adept powers at rating 0), which
        # the route reports as "Cannot import" too, instead of the 500 they used to cause.
        except (UnsupportedLegacyCharacterError, ValueError):
            expected[path.name] = False
    lines: list[str] = []
    for start in range(0, len(paths), uploads.MAX_FILES):
        batch = paths[start : start + uploads.MAX_FILES]
        response = upload(local, *[(p.name, p.read_bytes()) for p in batch])
        assert response.status_code == 200
        lines += results(response.text)
    assert len(lines) == len(paths)
    for path, line in zip(paths, lines, strict=True):
        if expected[path.name]:
            assert line.startswith(f"info: {path.name}: Character imported."), line
        else:
            assert line.startswith(f"error: {path.name}: Cannot import"), line
    assert any(expected.values())


# --- the quota -----------------------------------------------------------------------------------


def test_at_99_three_files_import_one_and_report_two_quota_errors(
    local: TestClient, store: Store
) -> None:
    stub = json.dumps({"biography": {"name": "Filler"}, "metatype_name": "Human"})
    for _ in range(99):
        store.create_character(owner(store), stub)
    response = upload(local, ("1.chum5", YETI), ("2.chum5", YETI), ("3.chum5", YETI))
    lines = results(response.text)
    assert lines[0].startswith("info: 1.chum5: Character imported.")
    assert lines[1:] == [
        f"error: {n}.chum5: You already have 100 characters, the most an account can store. "
        "Delete one to start another."
        for n in (2, 3)
    ]
    assert count(store) == 100
    # at quota, the list disables Upload
    assert re.search(r'<button type="submit" disabled[^>]*>Upload</button>', response.text)


# --- hardening and limits ------------------------------------------------------------------------


@pytest.mark.parametrize("payload", [ENTITY_BOMB, EXTERNAL_ENTITY])
def test_entity_declarations_are_refused_with_a_message(
    local: TestClient, store: Store, payload: bytes
) -> None:
    response = upload(local, ("evil.chum5", payload))
    assert response.status_code == 200
    assert results(response.text) == [
        "error: evil.chum5: Refused: the file declares XML entities or external references, "
        "which no Chummer save uses."
    ]
    assert count(store) == 0


def test_entity_refusal_on_the_export_page(local: TestClient) -> None:
    response = upload(local, ("evil.chum5", ENTITY_BOMB), open_it=True)
    assert (
        response.status_code == 200 and "Refused: the file declares XML entities" in response.text
    )


def test_an_oversized_file_is_refused_and_the_rest_still_import(
    local: TestClient, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHUMMER5_UPLOAD_MAX_MB", str(len(YETI) / (1024 * 1024) * 1.5))
    big = b"<" + b"x" * (len(YETI) * 3)
    response = upload(local, ("big.chum5", big), ("Yeti.chum5", YETI))
    lines = results(response.text)
    assert lines[0].startswith("error: big.chum5: Too large (the limit is")
    assert lines[1].startswith("info: Yeti.chum5: Character imported.")
    assert count(store) == 1


def test_the_parser_keeps_no_more_than_the_cap() -> None:
    """Past the cap nothing more of a file is kept: the spooled copy stops at the cap."""
    cap = 1000
    boundary = "XyZ"
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="big.json"\r\n'
        f"\r\n{'x' * 50_000}\r\n--{boundary}--\r\n"
    ).encode()

    async def stream() -> AsyncGenerator[bytes, None]:
        for i in range(0, len(body), 4096):
            yield body[i : i + 4096]

    headers = Headers({"content-type": f"multipart/form-data; boundary={boundary}"})
    parser = uploads._CappedParser(headers, stream(), cap)

    import asyncio

    form = asyncio.run(parser.parse())
    upload_file = form["files"]
    assert not isinstance(upload_file, str)
    assert id(upload_file) in parser.oversized
    upload_file.file.seek(0, 2)
    assert upload_file.file.tell() <= cap


def test_a_declared_body_over_the_limit_is_refused_before_reading(
    local: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHUMMER5_UPLOAD_MAX_MB", "0.001")
    response = local.post(
        UPLOAD,
        content=b"x" * 100,
        headers={
            "Content-Type": "multipart/form-data; boundary=XyZ",
            "Content-Length": str(10**9),
        },
    )
    assert results(response.text)[0].startswith("error: The upload is too large.")


def test_more_than_twenty_files_are_refused(local: TestClient, store: Store) -> None:
    files = [(f"{i}.json", b"{}") for i in range(uploads.MAX_FILES + 1)]
    response = upload(local, *files)
    assert results(response.text) == ["error: Too many files. Upload at most 20 at a time."]
    assert count(store) == 0


def test_bad_upload_size_setting_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from chummer5.store import config

    monkeypatch.setenv("CHUMMER5_UPLOAD_MAX_MB", "lots")
    with pytest.raises(ValueError, match="CHUMMER5_UPLOAD_MAX_MB"):
        config.upload_max_bytes()
    monkeypatch.setenv("CHUMMER5_UPLOAD_MAX_MB", "0")
    with pytest.raises(ValueError, match="above 0"):
        config.upload_max_bytes()


def test_import_chum5_takes_bytes_and_file_objects(tmp_path: Path) -> None:
    kwargs = dict(
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )
    from_path = import_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE), **kwargs)  # type: ignore[arg-type]
    from_bytes = import_chum5(YETI, **kwargs)  # type: ignore[arg-type]
    with mundane_fixture_path(PRIORITY_BUILD_FIXTURE).open("rb") as handle:
        from_file = import_chum5(handle, **kwargs)  # type: ignore[arg-type]
    assert from_path.save == from_bytes.save == from_file.save
