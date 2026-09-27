"""WP42: the cyberware subsystem/modification UI -- Phase K's last entry, and the first time the
browser can buy a rating-scaled implant or install a plugin into one.

`tests/unit/test_web_cyberware.py` (WP34) still covers the flat quantity-per-item half of the same
`POST /ui/cyberware` route and is deliberately left untouched: WP42 keeps `cyberware_{id}` meaning
exactly what it meant, so every one of those tests passing unchanged *is* the "additive, not
breaking" check. This module covers what is new -- the wider offered catalog, the per-unit rating
control, plugin installation against a live Capacity budget, and the character sheet's nested recap
with each conditional bonus's condition text.

Same "manual walkthrough; values match engine output for the same inputs" acceptance bar as
WP14-WP16/WP20/WP34's own test modules.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import metatype_choices
from chummer5.web.app import create_app
from chummer5.web.catalogs import (
    CYBERWARE_ENTRIES,
    CYBERWARE_PLUGIN_CHOICES,
    CYBERWARE_STANDALONE,
)

METATYPES = load_metatypes()
PRIORITIES = load_priorities()

BY_NAME = {entry.name: entry for entry in CYBERWARE_ENTRIES}
CYBEREYES = BY_NAME["Cybereyes Basic System"]
CYBEREARS = BY_NAME["Cyberears"]
VISION_ENHANCEMENT = BY_NAME["Vision Enhancement"]
SPATIAL_RECOGNIZER = BY_NAME["Spatial Recognizer"]
SYNTHETIC_FULL_LEG = BY_NAME["Synthetic Full Leg"]
SYNTHETIC_FULL_ARM = BY_NAME["Synthetic Full Arm"]
HYDRAULIC_JACKS = BY_NAME["Hydraulic Jacks"]
CUSTOMIZED_AGILITY = BY_NAME["Customized Agility"]
DATAJACK = BY_NAME["Datajack"]


PRIORITY_LETTERS = {
    "heritage_letter": "B",
    "attributes_letter": "C",
    "skills_letter": "D",
    "resources_letter": "A",
    "talent_letter": "E",
}


def _confirm_human(client: TestClient) -> None:
    """Heritage B / Resources A -- WP34's own test module uses Resources D, but Phase K purchases
    are expensive (a rating-3 Cybereyes plus a couple of plugins runs past D's 50,000¥ before any of
    these tests has made its point), and the five letters still have to be a valid A-E permutation.
    """
    client.get("/")
    human = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["B"], METATYPES)
        if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities", data={**PRIORITY_LETTERS, "metatype_id": human.metatype.id}
    )
    assert "Confirmed: Human" in response.text


def _compact(html: str) -> str:
    return re.sub(r"\s+", " ", html)


# --- the offered catalog -----------------------------------------------------------------------


def test_rating_scaled_items_are_offered_now_that_the_picker_reads_the_full_catalog() -> None:
    """Cybereyes/Cyberears are the whole point: before WP42 the picker offered WP31's flat 60 rows
    only, so the only subsystem parent a player could reach was a cyberlimb.
    """
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/ui/page/augmentation")

    assert f'name="cyberware_{CYBEREYES.id}"' in response.text
    assert f'name="cyberware_{CYBEREARS.id}"' in response.text


def test_requireparent_rows_are_not_offered_as_standalone_purchases() -> None:
    """`create_cyberware_tree_selection` rejects a `<requireparent>` item bought on its own, so
    WP34's picker offering four of them (Ocular Drone, Cyber Holster, Cyberarm Slide, Large
    Smuggling Compartment) could only ever produce an error. They live inside a parent now.
    """
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/ui/page/augmentation")

    assert CUSTOMIZED_AGILITY.requires_parent
    assert f'name="cyberware_{CUSTOMIZED_AGILITY.id}"' not in response.text
    assert not any(entry.requires_parent for entry in CYBERWARE_STANDALONE)


def test_engine_bookkeeping_rows_are_not_offered_at_all() -> None:
    offered = {entry.name for entry in CYBERWARE_STANDALONE}
    assert "Essence Hole" not in offered
    assert "Essence Antihole" not in offered
    assert all(
        "Essence Hole" not in {p.name for p in plugins}
        for plugins in CYBERWARE_PLUGIN_CHOICES.values()
    )


def test_a_parents_plugin_list_is_restricted_to_the_categories_it_allows() -> None:
    ear_plugins = {plugin.name for plugin in CYBERWARE_PLUGIN_CHOICES[CYBEREARS.id]}
    eye_plugins = {plugin.name for plugin in CYBERWARE_PLUGIN_CHOICES[CYBEREYES.id]}

    assert "Vision Enhancement" in eye_plugins
    assert "Vision Enhancement" not in ear_plugins  # Eyeware, and Cyberears allows only Earware
    # A bundled subsystem is auto-attached, so it is not offered as a choice in its own parent.
    assert "Image Link" not in eye_plugins
    assert "Sound Link" not in ear_plugins


# --- rating control ----------------------------------------------------------------------------


def test_a_bought_rated_item_gets_a_rating_control_over_its_real_range() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/cyberware", data={f"cyberware_{CYBEREYES.id}": "1"})

    assert f'name="cyberware_rating_{CYBEREYES.id}_0"' in response.text
    compact = _compact(response.text)
    for rating in (1, 2, 3, 4):
        assert f'<option value="{rating}"' in compact
    assert '<option value="5"' not in compact.split("cyberware_rating")[1].split("</select>")[0]


def test_the_chosen_rating_drives_the_price_and_the_essence_cost() -> None:
    """Cybereyes Basic System rating 3: 10,000¥ and 0.4 Essence
    (`4000 * Rating - 2000 * number(Rating > 1)`, `(Rating * 0.1) + 0.1`) -- the numbers WP36
    hand-checked against the p. 454 table.
    """
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/cyberware",
        data={f"cyberware_{CYBEREYES.id}": "1", f"cyberware_rating_{CYBEREYES.id}_0": "3"},
    )

    assert "10000¥, Essence 0.4" in _compact(response.text)
    sheet = client.get("/character/sheet")
    assert "Essence: 5.6 / 6." in sheet.text


def test_an_unrated_item_gets_no_rating_control() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/cyberware", data={f"cyberware_{DATAJACK.id}": "1"})

    assert f'name="cyberware_rating_{DATAJACK.id}_0"' not in response.text


def test_a_customization_rating_range_starts_at_the_limbs_floor_of_four() -> None:
    """`Customized Agility`'s `<minrating>` is `{AGIMinimum}+1`, i.e. the *limb's* base 3 plus one
    (p. 456/457) -- so the control must never offer 1-3, and defaulting a submitted-blank rating to
    1 would be an instant rejection rather than a sane default.
    """
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/cyberware", data={f"cyberware_{SYNTHETIC_FULL_ARM.id}": "1"})

    field = f"plugin_rating_{SYNTHETIC_FULL_ARM.id}_0_{CUSTOMIZED_AGILITY.id}"
    options = _compact(response.text).split(f'name="{field}"')[1].split("</select>")[0]
    assert '<option value="4"' in options
    assert '<option value="3"' not in options


# --- installing a plugin -----------------------------------------------------------------------


def test_installing_a_plugin_charges_capacity_and_nuyen_but_not_essence() -> None:
    """The Phase K mechanic, end to end through the browser: a Vision Enhancement bought as a
    subsystem costs the cybereyes' Capacity, is paid for in nuyen, and contributes zero Essence
    (`chummer5.engine.cyberware_subsystems`' dual-costing section).
    """
    client = TestClient(create_app())
    _confirm_human(client)
    bought_alone = client.post(
        "/ui/cyberware",
        data={f"cyberware_{CYBEREYES.id}": "1", f"cyberware_rating_{CYBEREYES.id}_0": "3"},
    )
    assert "Capacity 12 of 12 remaining" in _compact(bought_alone.text)

    response = client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{CYBEREYES.id}": "1",
            f"cyberware_rating_{CYBEREYES.id}_0": "3",
            f"plugin_{CYBEREYES.id}_0_{VISION_ENHANCEMENT.id}": "1",
            f"plugin_rating_{CYBEREYES.id}_0_{VISION_ENHANCEMENT.id}": "2",
        },
    )

    compact = _compact(response.text)
    # Rating 2: Capacity `Rating` = 2 of the eyes' `Rating * 4` = 12, and `Rating * 4000` = 8,000¥.
    assert "Capacity 10 of 12 remaining" in compact
    assert "(spent 18000)" in compact
    # Essence unchanged from the eyes' own 0.4 -- the plugin adds none.
    assert "Essence remaining: 5.6 / 6 (spent 0.4)" in compact


def test_an_over_capacity_plugin_set_is_rejected_with_the_engines_own_message() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    # Cyberears rating 1 -> a Capacity budget of 4. A rating-4 Select Sound Filter costs 4 and a
    # rating-1 Audio Enhancement 1 more. (WP126: both within Availability 12; a rating-6 filter,
    # this test's pre-WP126 case, is Availability 18 and now fails on that first.)
    filter_id = BY_NAME["Select Sound Filter"].id
    audio_id = BY_NAME["Audio Enhancement"].id
    response = client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{CYBEREARS.id}": "1",
            f"cyberware_rating_{CYBEREARS.id}_0": "1",
            f"plugin_{CYBEREARS.id}_0_{filter_id}": "1",
            f"plugin_rating_{CYBEREARS.id}_0_{filter_id}": "4",
            f"plugin_{CYBEREARS.id}_0_{audio_id}": "1",
            f"plugin_rating_{CYBEREARS.id}_0_{audio_id}": "1",
        },
    )

    assert response.status_code == 200
    assert "exceeding its Capacity budget" in response.text


def test_each_bought_unit_holds_its_own_plugins() -> None:
    """Two cyberlegs, a hydraulic jack in each -- the case the per-unit index exists for, and real
    fixture content (`Barrett.chum5`). One jack in one leg would be a different (and, per p. 457,
    bonus-less) purchase.
    """
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{SYNTHETIC_FULL_LEG.id}": "2",
            f"plugin_{SYNTHETIC_FULL_LEG.id}_0_{HYDRAULIC_JACKS.id}": "1",
            f"plugin_rating_{SYNTHETIC_FULL_LEG.id}_0_{HYDRAULIC_JACKS.id}": "2",
            f"plugin_{SYNTHETIC_FULL_LEG.id}_1_{HYDRAULIC_JACKS.id}": "1",
            f"plugin_rating_{SYNTHETIC_FULL_LEG.id}_1_{HYDRAULIC_JACKS.id}": "2",
        },
    )

    assert response.status_code == 200
    # 2 legs at 20,000 + 2 jacks at `Rating * 2500` = 5,000 each.
    assert "(spent 50000)" in _compact(response.text)
    sheet = client.get("/character/sheet")
    assert "Synthetic Full Leg × 2" in sheet.text


def test_a_bundled_subsystem_is_shown_as_included_rather_than_offered() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/cyberware", data={f"cyberware_{CYBEREYES.id}": "1"})

    assert "Included free: Image Link." in response.text


# --- carrying the tree forward ------------------------------------------------------------------


def test_committed_plugins_survive_a_full_page_re_render() -> None:
    """WP41 passed only the top-level ids to the picker, so a committed plugin was invisible in the
    form and the next submission dropped it. `to_requests()` is what fixes that.
    """
    client = TestClient(create_app())
    _confirm_human(client)
    client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{CYBEREYES.id}": "1",
            f"cyberware_rating_{CYBEREYES.id}_0": "3",
            f"plugin_{CYBEREYES.id}_0_{VISION_ENHANCEMENT.id}": "1",
            f"plugin_rating_{CYBEREYES.id}_0_{VISION_ENHANCEMENT.id}": "2",
        },
    )

    human = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["B"], METATYPES)
        if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities", data={**PRIORITY_LETTERS, "metatype_id": human.metatype.id}
    )
    response = client.get("/ui/page/augmentation")  # WP97

    compact = _compact(response.text)
    checkbox = f'name="plugin_{CYBEREYES.id}_0_{VISION_ENHANCEMENT.id}" value="1" checked'
    assert checkbox in compact
    assert "Capacity 10 of 12 remaining" in compact


def test_save_load_round_trips_a_plugin_purchase() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{CYBEREYES.id}": "1",
            f"cyberware_rating_{CYBEREYES.id}_0": "3",
            f"plugin_{CYBEREYES.id}_0_{VISION_ENHANCEMENT.id}": "1",
            f"plugin_rating_{CYBEREYES.id}_0_{VISION_ENHANCEMENT.id}": "2",
        },
    )
    save = client.get("/character/save")

    fresh = TestClient(create_app())
    fresh.get("/")
    loaded = fresh.post(
        "/character/load",
        files={"save_file": ("character.json", save.content, "application/json")},
    )

    assert "Character loaded." in loaded.text
    sheet = _compact(fresh.get("/character/sheet").text)
    assert "Cybereyes Basic System (Rating 3) × 1 — Capacity 2 of 12 used" in sheet
    assert "Vision Enhancement (Rating 2)" in sheet


# --- the character sheet -------------------------------------------------------------------------


def test_the_sheet_nests_a_plugin_under_the_parent_holding_it() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{CYBEREYES.id}": "1",
            f"cyberware_rating_{CYBEREYES.id}_0": "3",
            f"plugin_{CYBEREYES.id}_0_{VISION_ENHANCEMENT.id}": "1",
            f"plugin_rating_{CYBEREYES.id}_0_{VISION_ENHANCEMENT.id}": "2",
        },
    )

    sheet = _compact(client.get("/character/sheet").text)

    parent = "<li>Cybereyes Basic System (Rating 3) × 1 — Capacity 2 of 12 used"
    assert parent in sheet
    nested = sheet.split(parent)[1].split("</ul>")[0]
    assert "Vision Enhancement (Rating 2)" in nested
    assert "Image Link — included free" in nested


def test_the_sheet_prints_a_conditional_bonus_with_the_condition_it_applies_under() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/cyberware", data={f"cyberware_{SPATIAL_RECOGNIZER.id}": "1"})

    sheet = _compact(client.get("/character/sheet").text)

    assert "+2 Mental limit — Only for Perception to find the source of a sound" in sheet


def test_a_conditional_limit_row_appears_only_for_the_test_the_bonus_applies_to() -> None:
    """The point of the deliverable: a player can see the headline Mental limit *and* what it
    becomes for the one kind of test the implant helps with, without either number lying.
    """
    client = TestClient(create_app())
    _confirm_human(client)
    before = _compact(client.get("/character/sheet").text)
    headline = int(before.split("<th>Mental limit</th><td>")[1].split("<")[0])
    assert "Mental limit, visual Perception tests" not in before

    client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{CYBEREYES.id}": "1",
            f"cyberware_rating_{CYBEREYES.id}_0": "3",
            f"plugin_{CYBEREYES.id}_0_{VISION_ENHANCEMENT.id}": "1",
            f"plugin_rating_{CYBEREYES.id}_0_{VISION_ENHANCEMENT.id}": "2",
        },
    )

    after = _compact(client.get("/character/sheet").text)
    assert f"<th>Mental limit</th><td>{headline}</td>" in after  # headline unchanged
    assert f"<th>Mental limit, visual Perception tests</th><td>{headline + 2}</td>" in after
    # No bonus applies to hearing Perception, so no row restates the headline figure.
    assert "hearing Perception tests" not in after


def test_the_sheet_says_a_hydraulic_jacks_bonus_needs_a_matched_pair() -> None:
    """p. 457's pair rule is invisible in the data and WP40 models it in the engine; without this
    note a player reading two jacks' rows would count the printed +Rating twice.
    """
    client = TestClient(create_app())
    _confirm_human(client)
    client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{SYNTHETIC_FULL_LEG.id}": "2",
            f"plugin_{SYNTHETIC_FULL_LEG.id}_0_{HYDRAULIC_JACKS.id}": "1",
            f"plugin_rating_{SYNTHETIC_FULL_LEG.id}_0_{HYDRAULIC_JACKS.id}": "2",
            f"plugin_{SYNTHETIC_FULL_LEG.id}_1_{HYDRAULIC_JACKS.id}": "1",
            f"plugin_rating_{SYNTHETIC_FULL_LEG.id}_1_{HYDRAULIC_JACKS.id}": "2",
        },
    )

    sheet = _compact(client.get("/character/sheet").text)

    assert (
        "+2 Physical limit — Only for Gymnastics (Jumping) and Running (Sprinting) "
        "(granted once for a matched pair, not per implant)" in sheet
    )
    # And the engine really did grant it once: +2, not +4.
    headline = int(sheet.split("<th>Physical limit</th><td>")[1].split("<")[0])
    assert f"<th>Physical limit, Gymnastics (Jumping) tests</th><td>{headline + 2}</td>" in sheet


def test_two_identical_purchases_collapse_to_one_line_but_differing_ones_do_not() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{CYBEREARS.id}": "2",
            f"cyberware_rating_{CYBEREARS.id}_0": "1",
            f"cyberware_rating_{CYBEREARS.id}_1": "2",
        },
    )

    sheet = _compact(client.get("/character/sheet").text)
    assert "Cyberears (Rating 1) × 1" in sheet
    assert "Cyberears (Rating 2) × 1" in sheet
