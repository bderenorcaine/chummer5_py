"""WP29: Phase I's Magic-type/tradition/free-skill-grant/spell/power selection reaching the
browser (`POST /ui/talent`, `GET /ui/talent-options`, `POST /ui/spells`, `POST /ui/powers`), plus
the character sheet's new Magic section. Same "manual walkthrough; values match engine output for
the same inputs" acceptance bar as WP14-WP16/WP20's own test modules, plus the WP19-style
still-valid/now-invalid reconfirmation checks those modules already established for carried-forward
selections -- extended here to a carried-forward Talent selection specifically.

Neither of the corpus's 2 real magic fixtures (Miko, Wesson) can reach a full round-trip
`import_chum5()` success even after this WP (see `spec/worklogs/WP28.md` -- Miko for her own non-SR5
tradition, Wesson for an unrelated Karma-bought-attribute-points gap), so this module builds a
Magician and an Adept from scratch through the browser instead, using the same letter/codename
combinations those two fixtures use (`priorities.xml` letter B: Adept magic=6, Magician magic=4),
rather than trying to reproduce either fixture's exact numbers.
"""

from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import metatype_choices
from chummer5.engine.magic import mvp_power_catalog
from chummer5.web.app import create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
SPELLS = load_spells()
POWERS = load_powers()
MVP_POWERS = mvp_power_catalog(POWERS)
TRADITIONS = load_traditions()

HERMETIC = next(t for t in TRADITIONS if t.name == "Hermetic")
PISTOLS = next(s for s in SKILLS if s.name == "Pistols")
SPELLCASTING = next(s for s in SKILLS if s.name == "Spellcasting")
COUNTERSPELLING = next(s for s in SKILLS if s.name == "Counterspelling")
IMPROVED_POTENTIAL_PHYSICAL = next(
    p for p in MVP_POWERS if p.name == "Improved Potential (Physical)"
)
IMPROVED_PHYSICAL_ATTRIBUTE = next(p for p in MVP_POWERS if p.name == "Improved Physical Attribute")
SOME_SPELLS = SPELLS[:3]


def _compact(html: str) -> str:
    """Collapse inter-tag whitespace so a Jinja template's indentation doesn't defeat a substring
    assertion on rendered markup (e.g. `<td>Pistols</td>\\n          <td>4</td>`).
    """
    return re.sub(r">\s+<", "><", html)


def _confirm_human(client: TestClient, *, talent_letter: str) -> None:
    """Confirm a Human at Heritage A with `talent_letter` for Talent, and a fixed permutation of
    the remaining 3 letters (B/C/D/E minus whichever one was picked for Talent) for Attributes/
    Skills/Resources -- callers pick `talent_letter` to land Talent on whichever letter this test
    needs to offer Magician/Adept/Mundane (`priorities.xml`'s own real per-letter option lists, see
    `chummer5.engine.magic`'s module docstring).
    """
    client.get("/")
    remaining = [letter for letter in ("B", "C", "D", "E") if letter != talent_letter]
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "talent_letter": talent_letter,
            "attributes_letter": remaining[0],
            "skills_letter": remaining[1],
            "resources_letter": remaining[2],
            "metatype_id": human_choice.metatype.id,
        },
    )
    assert "Confirmed: Human" in response.text


def test_talent_section_before_confirmation_shows_a_placeholder() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert "Confirm a metatype and priorities above before selecting Talent." in response.text


def test_talent_defaults_to_mundane_at_letter_e_and_hides_spell_and_power_sections() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="E")

    response = client.get("/")

    assert "Not yet confirmed" in response.text
    assert 'value="Mundane"' in response.text
    assert "Adept Powers" not in response.text
    assert "<h2>Spells</h2>" not in response.text

    sheet = client.get("/character/sheet")
    assert "Type: Magician" not in sheet.text
    assert "Type: Adept" not in sheet.text


def test_magician_requires_a_tradition() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")

    response = client.post(
        "/ui/talent", data={"talent_letter": "B", "talent_codename": "Magician"}
    )

    assert "Magician requires a tradition" in response.text


def test_confirming_magician_sets_magic_rating_tradition_and_dice_pool_free_of_charge() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")

    response = client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Magician",
            "tradition_id": HERMETIC.id,
            "granted_skill_id": [SPELLCASTING.id, COUNTERSPELLING.id],
        },
    )

    assert response.status_code == 200
    assert "Confirmed: Magician (Hermetic)" in response.text
    assert "Magic 4" in response.text  # priorities.xml letter B's Magician option: magic=4

    # The sheet's skill table only ever renders once `character.skill_allocation` is committed
    # (the same "None until committed" gate every other section has) -- a zero-point submission is
    # enough, since the granted skill's rating comes entirely from an Improvement, not from points
    # spent here (see chummer5.engine.magic.apply_magic_skill_grant_improvements's own docstring).
    client.post("/ui/skills", data={})
    sheet = client.get("/character/sheet")
    assert "Type: Magician" in sheet.text
    assert "Magic rating: 4" in sheet.text
    assert "Tradition: Hermetic" in sheet.text
    # Hermetic Drain Resistance = LOG + WIL = 1 + 1 (Human's metatype minimums, no points spent).
    assert "Drain Resistance: 2" in sheet.text
    assert "<td>Spellcasting</td><td>4</td>" in _compact(sheet.text)
    assert "<td>Counterspelling</td><td>4</td>" in _compact(sheet.text)


def test_confirming_adept_sets_magic_rating_and_power_points() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")

    response = client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Adept",
            "granted_skill_id": [PISTOLS.id],
        },
    )

    assert response.status_code == 200
    assert "Confirmed: Adept" in response.text
    assert "Magic 6" in response.text  # priorities.xml letter B's Adept option: magic=6

    client.post("/ui/skills", data={})  # see the identical comment in the Magician test above
    sheet = client.get("/character/sheet")
    assert "Type: Adept" in sheet.text
    assert "Magic rating: 6" in sheet.text
    assert "Power Points: 6" in sheet.text
    # Adept Drain Resistance is fixed BOD + WIL = 1 + 1, independent of tradition.
    assert "Drain Resistance: 2" in sheet.text
    assert "<td>Pistols</td><td>4</td>" in _compact(sheet.text)


def test_spell_selection_within_budget_shows_on_the_sheet() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")
    client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Magician",
            "tradition_id": HERMETIC.id,
            "granted_skill_id": [SPELLCASTING.id, COUNTERSPELLING.id],
        },
    )

    response = client.post(
        "/ui/spells", data={"spell_id": [s.id for s in SOME_SPELLS]}
    )

    assert response.status_code == 200
    assert f"Spells chosen: {len(SOME_SPELLS)} / 7" in response.text  # letter B Magician: spells=7

    sheet = client.get("/character/sheet")
    for spell in SOME_SPELLS:
        assert spell.name in sheet.text


def test_spell_selection_over_budget_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")
    client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Magician",
            "tradition_id": HERMETIC.id,
            "granted_skill_id": [SPELLCASTING.id, COUNTERSPELLING.id],
        },
    )

    response = client.post("/ui/spells", data={"spell_id": [s.id for s in SPELLS[:8]]})

    assert "exceeding the budget of 7" in response.text


def test_power_selection_flat_bonus_raises_physical_limit() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")
    client.post(
        "/ui/talent",
        data={"talent_letter": "B", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )
    baseline_sheet = client.get("/character/sheet")
    assert "<th>Physical limit</th><td>2</td>" in _compact(baseline_sheet.text)

    response = client.post(
        "/ui/powers",
        data={f"power_rating_{IMPROVED_POTENTIAL_PHYSICAL.id}": "1"},
    )

    assert response.status_code == 200
    assert "Power Points spent: 0.5 / 6" in response.text

    sheet = client.get("/character/sheet")
    assert "<th>Physical limit</th><td>3</td>" in _compact(sheet.text)


def test_power_selection_select_attribute_shape_raises_the_chosen_attribute() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")
    client.post(
        "/ui/talent",
        data={"talent_letter": "B", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )

    response = client.post(
        "/ui/powers",
        data={
            f"power_rating_{IMPROVED_PHYSICAL_ATTRIBUTE.id}": "2",
            f"power_attribute_{IMPROVED_PHYSICAL_ATTRIBUTE.id}": "BOD",
        },
    )

    assert response.status_code == 200
    sheet = client.get("/character/sheet")
    assert "<tr><td>BOD</td><td>3</td></tr>" in _compact(sheet.text)


def test_power_selection_over_budget_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")
    client.post(
        "/ui/talent",
        data={"talent_letter": "B", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )

    # Individually each pick fits its own per-power cap (Improved Physical Attribute's rulebook
    # cap is min(power.limit=12, budget=6) = 6; Improved Potential (Physical) is levels=False, so
    # its only legal rating is 1) -- their *combined* cost (6 * 1 + 0.5 * 1 = 6.5) is what exceeds
    # the 6-point budget, exercising the total-spend check rather than either pick's own range.
    response = client.post(
        "/ui/powers",
        data={
            f"power_rating_{IMPROVED_PHYSICAL_ATTRIBUTE.id}": "6",
            f"power_attribute_{IMPROVED_PHYSICAL_ATTRIBUTE.id}": "BOD",
            f"power_rating_{IMPROVED_POTENTIAL_PHYSICAL.id}": "1",
        },
    )

    assert "exceeding the budget of 6" in response.text


def test_attribute_resubmission_preserves_the_carried_forward_magic_selection() -> None:
    """The relink WP29 adds to `submit_attributes` (`_relink_magic_selection`) -- without it, a
    Magician/Adept's entire Talent selection would silently reset to Mundane on the very next
    attribute edit, since `submit_attributes` still rebuilds via `create_character()` fresh
    (WP19 left it that way; see that WP's own worklog).
    """
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")
    client.post(
        "/ui/talent",
        data={"talent_letter": "B", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )
    client.post(
        "/ui/powers", data={f"power_rating_{IMPROVED_POTENTIAL_PHYSICAL.id}": "1"}
    )

    response = client.post("/ui/attributes", data={"attr_BOD": "2"})

    assert response.status_code == 200
    client.post("/ui/skills", data={})  # see the identical comment in the Magician test above
    sheet = client.get("/character/sheet")
    assert "Type: Adept" in sheet.text
    assert "Magic rating: 6" in sheet.text
    assert "<td>Pistols</td><td>4</td>" in _compact(sheet.text)
    # BOD rose from the attribute edit (1 -> 3), and physical_limit still reflects the carried
    # forward Improved Potential (Physical) power's +1 on top of the new BOD-derived total.
    assert "<tr><td>BOD</td><td>3</td></tr>" in _compact(sheet.text)


def test_talent_change_resets_spell_and_power_selection() -> None:
    """A (re)confirmed Talent selection resets `spell_selection`/`power_selection` -- see
    `chummer5.web.app._replace_committed_talent`'s own docstring for why a changed archetype can't
    carry forward a spell/power budget that may no longer even apply.
    """
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")
    client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Magician",
            "tradition_id": HERMETIC.id,
            "granted_skill_id": [SPELLCASTING.id, COUNTERSPELLING.id],
        },
    )
    client.post("/ui/spells", data={"spell_id": [SOME_SPELLS[0].id]})
    sheet_before = client.get("/character/sheet")
    assert SOME_SPELLS[0].name in sheet_before.text

    response = client.post(
        "/ui/talent",
        data={"talent_letter": "B", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )

    assert response.status_code == 200
    sheet_after = client.get("/character/sheet")
    assert "Type: Adept" in sheet_after.text
    assert SOME_SPELLS[0].name not in sheet_after.text


def test_priorities_reconfirmation_carries_forward_magic_and_flags_staleness() -> None:
    """Mirrors WP19's own still-valid/now-invalid reconfirmation checks: moving Talent to a letter
    that no longer offers the committed codename doesn't reset `character.magic_type` outright --
    it carries forward and is surfaced as a distinct staleness warning instead, consistent with
    every other carried-forward selection this project already treats this way.
    """
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")
    client.post(
        "/ui/talent",
        data={"talent_letter": "B", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    # Swap Talent onto letter E (Mundane-only) and Resources onto B (where Talent used to be) --
    # still a valid A-E permutation, Attributes/Skills unchanged.
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "talent_letter": "E",
            "attributes_letter": "C",
            "skills_letter": "D",
            "resources_letter": "B",
            "metatype_id": human_choice.metatype.id,
        },
    )

    assert response.status_code == 200
    assert "No longer fits since priorities were last confirmed" in response.text
    assert "Reconfirm Talent below to continue" in response.text

    sheet = client.get("/character/sheet")
    assert "Type: Adept" in sheet.text  # carried forward, not silently reset


def test_confirming_an_unoffered_codename_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="E")

    response = client.post(
        "/ui/talent", data={"talent_letter": "E", "talent_codename": "Adept"}
    )

    assert "is not an offered Talent option at letter" in response.text


# -- Post-WP29 correction: Special Attribute Points spent raising MAG --------------------------
# Core rulebook p.65: Special Attribute Points "may be split... between... Edge and Magic or
# Resonance." See spec/rulebooks/learnings.md's "Post-WP29 correction" entry for the full research.


def test_attribute_form_shows_no_mag_row_for_mundane() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="E")

    response = client.get("/")

    assert 'name="attr_MAG"' not in response.text


def test_attribute_form_shows_a_mag_row_once_talent_is_confirmed() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="C")  # letter C Adept: magic=4, metatype max 6
    client.post(
        "/ui/talent",
        data={"talent_letter": "C", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )

    response = client.get("/")

    assert 'name="attr_MAG"' in response.text


def test_spending_special_attribute_points_on_mag_raises_the_total() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="C")  # Adept: magic=4, headroom to 6
    client.post(
        "/ui/talent",
        data={"talent_letter": "C", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )

    response = client.post("/ui/attributes", data={"attr_MAG": "2"})

    assert response.status_code == 200
    assert "<td>MAG</td><td><input" in _compact(response.text)

    sheet = client.get("/character/sheet")
    assert "Magic rating: 6" in sheet.text
    assert "Power Points: 6" in sheet.text


def test_mag_points_cannot_exceed_the_metatypes_own_magic_maximum() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="C")  # Adept: magic=4, max 6 -> only 2 points of headroom
    client.post(
        "/ui/talent",
        data={"talent_letter": "C", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )

    response = client.post("/ui/attributes", data={"attr_MAG": "3"})

    assert "exceed the metatype&#39;s Magic maximum" in response.text


def test_edg_and_mag_share_one_special_attribute_points_budget() -> None:
    """Confirms the cross-check specifically -- both EDG=1 and MAG=1 individually fit their own
    per-attribute range/maximum easily, but their *combined* cost (2) exceeds Human's Heritage-E
    special-attribute-points budget (1, hand-checked against `priorities.xml`).
    """
    client = TestClient(create_app())
    client.get("/")
    heritage = PRIORITIES.heritage["E"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "E",
            "talent_letter": "D",  # letter D Adept: magic=2, headroom to 6
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "A",
            "metatype_id": human_choice.metatype.id,
        },
    )
    assert "Confirmed: Human" in response.text
    client.post(
        "/ui/talent",
        data={"talent_letter": "D", "talent_codename": "Adept", "granted_skill_id": []},
    )

    response = client.post("/ui/attributes", data={"attr_EDG": "1", "attr_MAG": "1"})

    assert "special-attribute-points budget of 1" in response.text


def test_talent_resubmission_resets_magic_attribute_points() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="C")
    client.post(
        "/ui/talent",
        data={"talent_letter": "C", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )
    client.post("/ui/attributes", data={"attr_MAG": "2"})
    sheet_before = client.get("/character/sheet")
    assert "Magic rating: 6" in sheet_before.text

    client.post(
        "/ui/talent",
        data={"talent_letter": "C", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )

    sheet_after = client.get("/character/sheet")
    assert "Magic rating: 4" in sheet_after.text  # back to the raw Talent-granted rating
    response = client.get("/")
    # The MAG row's own points input reset to 0 -- match regardless of attribute
    # order/whitespace inside the <input> tag itself (unlike inter-tag whitespace, `_compact`
    # doesn't normalize that).
    match = re.search(r'name="attr_MAG"[^>]*value="(\d+)"', response.text)
    assert match is not None
    assert match.group(1) == "0"


def test_attribute_resubmission_preserves_spent_magic_attribute_points() -> None:
    """Mirrors `test_attribute_resubmission_preserves_the_carried_forward_magic_selection` above,
    but for the newer `magic_attribute_points` field specifically -- an unrelated primary-attribute
    edit must not silently drop MAG points already spent.
    """
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="C")
    client.post(
        "/ui/talent",
        data={"talent_letter": "C", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )
    client.post("/ui/attributes", data={"attr_MAG": "2"})

    response = client.post("/ui/attributes", data={"attr_MAG": "2", "attr_BOD": "1"})

    assert response.status_code == 200
    sheet = client.get("/character/sheet")
    assert "Magic rating: 6" in sheet.text


def test_save_load_round_trip_preserves_magic_attribute_points() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="C")
    client.post(
        "/ui/talent",
        data={"talent_letter": "C", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )
    client.post("/ui/attributes", data={"attr_MAG": "2"})

    save_response = client.get("/character/save")
    save_data = json.loads(save_response.content)
    assert save_data["magic_attribute_points"] == 2

    fresh_client = TestClient(create_app())
    fresh_client.get("/")
    load_response = fresh_client.post(
        "/character/load",
        files={"save_file": ("character.json", save_response.content, "application/json")},
    )
    assert "Character loaded." in load_response.text
    sheet = fresh_client.get("/character/sheet")
    assert "Magic rating: 6" in sheet.text
    assert "Power Points: 6" in sheet.text
