"""WP45: the bioware purchase UI, folded into the same `POST /ui/cyberware` route/`_cyberware.html`
section as cyberware (see `chummer5.web.app._cyberware_context`'s own docstring for why bioware
folds in rather than getting its own peer section, unlike Lifestyle). Backed directly by
`chummer5.engine.bioware.create_bioware_selection`/`apply_bioware_improvements`, sharing both the
nuyen budget (gear+Lifestyle+cyberware+bioware) and the Essence pool (cyberware+bioware) that
`chummer5.engine.resources`/`chummer5.engine.bioware` already establish.

Same "manual walkthrough; values match engine output for the same inputs" acceptance bar as
`tests/unit/test_web_cyberware.py`'s own module, plus the cross-selection interaction tests unique
to bioware sharing a section with cyberware (the shared Essence floor, the fixed cyberware-first/
bioware-second evaluation order).
"""

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import metatype_choices
from chummer5.web.app import BIOWARE, CYBERWARE, create_app
from chummer5.web.catalogs import SKILLS

METATYPES = load_metatypes()
PRIORITIES = load_priorities()

CATS_EYES = next(b for b in BIOWARE if b.name == "Cat's Eyes")
ENHANCED_ARTICULATION = next(b for b in BIOWARE if b.name == "Enhanced Articulation")
SLEEP_REGULATOR = next(b for b in BIOWARE if b.name == "Sleep Regulator")
REFLEX_RECORDER = next(b for b in BIOWARE if b.name == "Reflex Recorder")
SYNTHETIC_FULL_ARM = next(c for c in CYBERWARE if c.name == "Synthetic Full Arm")
SUBMACHINE_GUN = next(c for c in CYBERWARE if c.name == "Submachine Gun")


def _squash(text: str) -> str:
    """Collapse whitespace, so an assertion about rendered markup doesn't depend on how Jinja
    happens to indent it (WP80)."""
    return " ".join(text.split())


def _confirm_human(client: TestClient) -> None:
    """Same Heritage A / Attributes B / Skills C / Resources D combination
    `tests/unit/test_web_cyberware.py`'s own helper uses, giving each test here a known, real nuyen
    budget to check against.
    """
    client.get("/")
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )
    assert "Confirmed: Human" in response.text


def test_index_after_confirmation_lists_every_bioware_catalog_item() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/ui/page/augmentation")

    # Jinja2 autoescapes the apostrophe as `&#39;`.
    assert "Cat&#39;s Eyes" in response.text
    assert "Enhanced Articulation" in response.text


def test_buying_a_bioware_item_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/cyberware", data={f"bioware_{CATS_EYES.id}": "1"})

    assert response.status_code == 200
    assert f"{CATS_EYES.cost}" in response.text
    sheet = client.get("/character/sheet")
    assert "Cat&#39;s Eyes × 1" in sheet.text
    # Essence 6 - 0.1 == 5.9.
    assert "Essence: 5.9 / 6." in sheet.text


def test_buying_cyberware_and_bioware_together_shares_one_essence_pool() -> None:
    """The whole point of folding bioware into cyberware's own section: one submission can buy
    both, and their Essence costs stack against the same pool.
    """
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{SYNTHETIC_FULL_ARM.id}": "1",  # Essence 1
            f"bioware_{CATS_EYES.id}": "1",  # Essence 0.1
        },
    )

    assert response.status_code == 200
    sheet = client.get("/character/sheet")
    assert "Synthetic Full Arm × 1" in sheet.text
    assert "Cat&#39;s Eyes × 1" in sheet.text
    # 6 - 1 - 0.1 == 4.9.
    assert "Essence: 4.9 / 6." in sheet.text


def test_bioware_essence_floor_accounts_for_already_bought_cyberware() -> None:
    """The shared-Essence-floor interaction `chummer5.engine.bioware`'s module docstring documents:
    cyberware is resolved first (5 Submachine Guns, Essence 5), leaving only 1 Essence of headroom
    -- a bioware purchase that alone would fit (Enhanced Articulation, Essence 0.3) still fits here,
    but adding Suprathyroid-Gland-sized headroom would not (no such item is offered, so instead this
    proves the *other* direction: buying enough cyberware first that a *smaller* remaining floor is
    what bioware's own check sees, not BASE_ESSENCE fresh).
    """
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{SUBMACHINE_GUN.id}": "5",  # Essence 5, nuyen 24000 -- well under budget
            f"bioware_{ENHANCED_ARTICULATION.id}": "1",  # Essence 0.3
        },
    )

    assert response.status_code == 200
    sheet = client.get("/character/sheet")
    assert "Submachine Gun × 5" in sheet.text
    assert "Enhanced Articulation × 1" in sheet.text
    # 6 - 5 - 0.3 == 0.7.
    assert "Essence: 0.7 / 6." in sheet.text


def test_bioware_essence_floor_rejects_when_combined_with_cyberware_exceeds_it() -> None:
    """A combination invalid only once cyberware AND bioware are counted together -- confirms the
    fixed cyberware-first/bioware-second evaluation order actually catches it (on the bioware call),
    per `chummer5.engine.bioware`'s own module docstring.
    """
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{SUBMACHINE_GUN.id}": "6",  # Essence 6 alone -- already at the floor
            f"bioware_{CATS_EYES.id}": "1",  # Essence 0.1 -- pushes combined total over
        },
    )

    assert response.status_code == 200
    assert "would leave no Essence remaining" in response.text
    # Rejected as a whole -- neither purchase is committed.
    sheet = client.get("/character/sheet")
    assert "None installed." in sheet.text


def test_bioware_flat_bonus_raises_physical_limit() -> None:
    """Enhanced Articulation's `<physicallimit>1</physicallimit>` flat bonus reaches the character
    sheet's Physical Limit, the same way a Cyberlimb's `PHYSICAL_CM` bonus already does for
    cyberware -- proving `apply_bioware_improvements` actually applies a real `FLAT_BONUS` item's
    Improvements, not just its Essence cost.
    """
    client = TestClient(create_app())
    _confirm_human(client)
    sheet_before = client.get("/character/sheet")
    base_limit = int(sheet_before.text.split("Physical limit</th><td>")[1].split("<")[0])

    client.post("/ui/cyberware", data={f"bioware_{ENHANCED_ARTICULATION.id}": "1"})

    sheet_after = client.get("/character/sheet")
    new_limit = int(sheet_after.text.split("Physical limit</th><td>")[1].split("<")[0])
    assert new_limit == base_limit + 1


def test_unknown_bioware_catalog_id_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/cyberware", data={"bioware_not-a-real-id": "1"})

    # Mirrors _parse_cyberware's identical "unknown keys are just not in the catalog to iterate"
    # shape -- a no-op submission, not a rejection.
    assert response.status_code == 200
    sheet = client.get("/character/sheet")
    assert "None installed." in sheet.text


def test_reconfirming_priorities_keeps_the_bioware_selection() -> None:
    """WP19's re-validate-in-place precedent applies to bioware too, mirroring
    `test_web_cyberware.py`'s identical cyberware test.
    """
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/cyberware", data={f"bioware_{SLEEP_REGULATOR.id}": "1"})

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "D",
            "resources_letter": "C",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )
    response = client.get("/ui/page/augmentation")  # WP97

    assert f'name="bioware_{SLEEP_REGULATOR.id}"\n                value="1"' in response.text
    sheet = client.get("/character/sheet")
    assert "Sleep Regulator × 1" in sheet.text


def test_save_load_round_trips_bioware_selection() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/cyberware", data={f"bioware_{SLEEP_REGULATOR.id}": "1"})

    save_response = client.get("/character/save")
    assert save_response.status_code == 200

    fresh_client = TestClient(create_app())
    fresh_client.get("/")
    load_response = fresh_client.post(
        "/character/load",
        files={"save_file": ("character.json", save_response.content, "application/json")},
    )

    assert "Character loaded." in load_response.text
    sheet = fresh_client.get("/character/sheet")
    assert "Sleep Regulator × 1" in sheet.text


# --- WP80: Reflex Recorder's purchase-time skill picker -------------------------------------------


def test_reflex_recorder_row_offers_a_skill_picker_only_once_bought() -> None:
    """The picker is per bought *unit*, so an unbought row shows no dropdown at all -- 28 `<option>`
    elements for a row nobody has bought would be noise on every render of this section.
    """
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/cyberware", data={f"bioware_{REFLEX_RECORDER.id}": "0"})
    assert f"bioware_skill_{REFLEX_RECORDER.id}_0" not in response.text

    response = client.post("/ui/cyberware", data={f"bioware_{REFLEX_RECORDER.id}": "1"})
    assert f"bioware_skill_{REFLEX_RECORDER.id}_0" in response.text
    assert "Longarms (AGI)" in response.text
    # The `limittoattribute` filter, visible in the offered options: no LOG-linked skill.
    assert "Computer (LOG)" not in response.text


def test_buying_a_reflex_recorder_with_a_chosen_skill_raises_that_skills_pool() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    # Buy 3 points of Longarms first, so the sheet shows a real rating to compare against.
    longarms = next(s for s in SKILLS if s.name == "Longarms")
    client.post("/ui/skills", data={f"skill_{longarms.id}": "3"})
    sheet = client.get("/character/sheet")
    assert "<td>Longarms</td> <td>3</td>" in _squash(sheet.text)

    response = client.post(
        "/ui/cyberware",
        data={
            f"bioware_{REFLEX_RECORDER.id}": "1",
            f"bioware_skill_{REFLEX_RECORDER.id}_0": "Longarms",
        },
    )
    assert response.status_code == 200
    assert 'value="Longarms" selected' in _squash(response.text)

    sheet = client.get("/character/sheet")
    assert "Reflex Recorder (Longarms) × 1" in sheet.text
    # WP82: `bought (with bonuses)` -- 3 points bought, the implant's +1 on top.
    assert "<td>Longarms</td> <td>3 (4)</td>" in _squash(sheet.text)


def test_buying_a_reflex_recorder_without_choosing_a_skill_is_an_error() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/cyberware", data={f"bioware_{REFLEX_RECORDER.id}": "1"})

    assert "Reflex Recorder requires a chosen skill" in response.text
    sheet = client.get("/character/sheet")
    assert "Reflex Recorder" not in sheet.text


def test_two_reflex_recorders_pick_independently_and_reject_a_repeated_skill() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/cyberware",
        data={
            f"bioware_{REFLEX_RECORDER.id}": "2",
            f"bioware_skill_{REFLEX_RECORDER.id}_0": "Longarms",
            f"bioware_skill_{REFLEX_RECORDER.id}_1": "Longarms",
        },
    )
    assert "only one per skill" in response.text

    response = client.post(
        "/ui/cyberware",
        data={
            f"bioware_{REFLEX_RECORDER.id}": "2",
            f"bioware_skill_{REFLEX_RECORDER.id}_0": "Longarms",
            f"bioware_skill_{REFLEX_RECORDER.id}_1": "Sneaking",
        },
    )
    assert response.status_code == 200
    sheet = client.get("/character/sheet")
    assert "Reflex Recorder (Longarms) × 1" in sheet.text
    assert "Reflex Recorder (Sneaking) × 1" in sheet.text


def test_save_load_round_trips_a_reflex_recorders_chosen_skill() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post(
        "/ui/cyberware",
        data={
            f"bioware_{REFLEX_RECORDER.id}": "1",
            f"bioware_skill_{REFLEX_RECORDER.id}_0": "Longarms",
        },
    )

    save_response = client.get("/character/save")
    fresh_client = TestClient(create_app())
    fresh_client.get("/")
    load_response = fresh_client.post(
        "/character/load",
        files={"save_file": ("character.json", save_response.content, "application/json")},
    )

    assert "Character loaded." in load_response.text
    sheet = fresh_client.get("/character/sheet")
    assert "Reflex Recorder (Longarms) × 1" in sheet.text


def test_reconfirming_priorities_keeps_a_reflex_recorders_chosen_skill() -> None:
    """The full-page re-render path (`chummer5.web.routes.priorities`) rebuilds this section's rows
    from the committed selection -- WP80 made that carry requests, not bare ids, so the pick has to
    still be selected afterwards rather than silently reverting to "— choose a skill —".
    """
    client = TestClient(create_app())
    _confirm_human(client)
    client.post(
        "/ui/cyberware",
        data={
            f"bioware_{REFLEX_RECORDER.id}": "1",
            f"bioware_skill_{REFLEX_RECORDER.id}_0": "Longarms",
        },
    )

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "D",
            "resources_letter": "C",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )
    response = client.get("/ui/page/augmentation")  # WP97

    assert 'value="Longarms" selected' in _squash(response.text)
    sheet = client.get("/character/sheet")
    assert "Reflex Recorder (Longarms) × 1" in sheet.text
