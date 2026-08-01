"""Cross-checks WP78's attribute/Initiative-Dice cyberware bonuses against the legacy-computed
`<totalvalue>` in the real `.chum5` corpus.

The oracle these tests use is the one thing the corpus is unambiguously good at: an attribute's
`<totalvalue>` is the *augmented* figure the legacy engine computed, while `<base>` is what the
player bought (see `spec/worklogs/WP6.md`'s own note on the distinction, which is exactly why
`tests/integration/test_character_fixtures.py` skips every attribute where the two differ). WP78 is
the first WP in this project that can reproduce a `totalvalue != base + metatypemin` case at all --
so these three fixtures move from "skipped as out of scope" to "checked."

Same "read the raw XML by hand, replay the SR5 subset" approach as
`tests/integration/test_cyberware_tree_fixtures.py`, and for the same reason: none of these three is
`buildmethod == Priority`, so `create_character` can't build them from their own letters. Each test
rebuilds the fixture's attribute *spend* on a Priority character, replays the augmentation purchase
this WP models, and compares the resulting REA against the legacy number.

Only REA is asserted. AGI/STR diverge in all three fixtures for reasons entirely outside this WP
(cyberlimb averaging, rating-scaled Muscle Toner bioware -- neither modeled), and asserting them
would be asserting somebody else's gap.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from tests.fixtures.mundane_chum5 import mundane_fixture_path

from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.cyberware_subsystems import (
    CyberwarePurchaseRequest,
    apply_cyberware_tree_improvements,
    create_cyberware_tree_selection,
)
from chummer5.engine.derived import BASE_INITIATIVE_DICE, initiative_dice, initiative_value

ENTRIES = load_cyberware_entries()
BY_NAME = {entry.name: entry for entry in ENTRIES}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()

# Every attribute a Priority character allocates points to, so a fixture's own spend can be
# replayed verbatim rather than hand-transcribed per test.
_SPENDABLE = ("BOD", "AGI", "REA", "STR", "CHA", "INT", "LOG", "WIL")


def _fixture_attributes(fixture_name: str) -> dict[str, tuple[int, int]]:
    """`{code: (points bought, legacy-computed total)}` for one fixture."""
    root = ET.parse(mundane_fixture_path(fixture_name)).getroot()
    return {
        attribute.findtext("name", ""): (
            int(attribute.findtext("base", "0")),
            int(attribute.findtext("totalvalue", "0")),
        )
        for attribute in root.iter("attribute")
    }


def _fixture_cyberware(fixture_name: str) -> list[tuple[str, int, str]]:
    """`[(name, rating, grade), ...]` for every top-level `<cyberware>` in one fixture."""
    root = ET.parse(mundane_fixture_path(fixture_name)).getroot()
    cyberwares = root.find(".//cyberwares")
    assert cyberwares is not None
    return [
        (
            item.findtext("name", ""),
            int(item.findtext("rating", "0") or 0),
            item.findtext("grade", ""),
        )
        for item in cyberwares.findall("cyberware")
    ]


def _character(metatype_name: str, points: dict[str, int]) -> Character:
    heritage = PRIORITIES.heritage["A"]
    choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == metatype_name
    )
    return create_character(
        metatype_choice=choice,
        heritage_letter="A",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points=points,
    )


def _replay(fixture_name: str, metatype_name: str, purchases: list[tuple[str, int]]) -> Character:
    attributes = _fixture_attributes(fixture_name)
    return _replay_with_points(
        metatype_name,
        {code: attributes[code][0] for code in _SPENDABLE if code in attributes},
        purchases,
    )


def _replay_with_points(
    metatype_name: str, points: dict[str, int], purchases: list[tuple[str, int]]
) -> Character:
    """`_replay` with the attribute spend supplied directly instead of read off a fixture -- for
    the WP81 case that needs one attribute moved to its natural maximum while everything else
    about the replay stays the fixture's own.
    """
    character = _character(metatype_name, points)
    selection = create_cyberware_tree_selection(
        [
            CyberwarePurchaseRequest(item_id=BY_NAME[name].id, rating=rating)
            for name, rating in purchases
        ],
        ENTRIES,
        10_000_000,  # the fixtures' own nuyen budgets are a SumtoTen concern, not this WP's
    )
    apply_cyberware_tree_improvements(character, selection)
    return character


def test_blues_rating_2_reaction_enhancers_match_its_legacy_reaction_total() -> None:
    """`BLUE.chum5` (Ork) buys Rating 2 Reaction Enhancers and nothing else that touches REA. Its
    REA `<base>` is 0 -- so the Ork minimum of 1 plus the implant's +2 is the legacy `<totalvalue>`
    of 3, and this is the plainest possible check that the bonus lands at all.
    """
    assert ("Reaction Enhancers", 2, "Used") in _fixture_cyberware("BLUE.chum5")
    attributes = _fixture_attributes("BLUE.chum5")
    assert attributes["REA"] == (0, 3)  # bought nothing, ended at 3

    character = _replay("BLUE.chum5", "Ork", [("Reaction Enhancers", 2)])
    assert character.attribute_value("REA") == 3
    # p. 455's parenthesis, checked rather than assumed: Initiative follows REA automatically.
    assert initiative_value(character) == 3 + character.attribute_value("INT")
    assert initiative_dice(character) == BASE_INITIATIVE_DICE  # nothing here grants a die


def test_scsi_owns_both_reaction_augmentations_and_legacy_stacks_neither() -> None:
    """The sharpest fixture in the corpus for this WP: `SCSi.chum5` (Human) owns **both** Wired
    Reflexes Rating 1 and Reaction Enhancers Rating 1, at Standard grade. Its REA `<base>` is 1, so
    the natural rating is 2 -- and the legacy-computed `<totalvalue>` is **3, not 4**.

    That single number is the whole justification for carrying `precedence="0"` through to
    `Improvement.unique_name` (p. 455: reaction enhancers are "incompatible with all other
    enhancements to Reaction, including wired reflexes"). Without it this engine would produce 4,
    which is both wrong per the book and a diff against the oracle.
    """
    cyberware = _fixture_cyberware("SCSi.chum5")
    assert ("Wired Reflexes", 1, "Standard") in cyberware
    assert ("Reaction Enhancers", 1, "Standard") in cyberware
    attributes = _fixture_attributes("SCSi.chum5")
    assert attributes["REA"] == (1, 3)

    character = _replay("SCSi.chum5", "Human", [("Wired Reflexes", 1), ("Reaction Enhancers", 1)])
    assert character.attribute_value("REA") == 3
    # The Initiative *Dice* half has no competitor -- only wired reflexes grants any.
    assert initiative_dice(character) == BASE_INITIATIVE_DICE + 1


def test_fuzzys_wired_reflexes_match_its_legacy_reaction_total() -> None:
    """`Fuzzy-chargen.chum5` (Human) buys REA up to 5 with points and adds Wired Reflexes Rating 1,
    reaching the legacy `<totalvalue>` of 6 -- which is also Human's natural REA maximum, so this
    fixture happens to sit exactly on the boundary discussed in `spec/decisions-log.md`'s
    2026-07-31 augmented-maximum entry rather than past it.
    """
    assert ("Wired Reflexes", 1, "Standard") in _fixture_cyberware("Fuzzy-chargen.chum5")
    attributes = _fixture_attributes("Fuzzy-chargen.chum5")
    assert attributes["REA"] == (4, 6)

    character = _replay("Fuzzy-chargen.chum5", "Human", [("Wired Reflexes", 1)])
    assert character.attribute_value("REA") == 6
    assert initiative_dice(character) == BASE_INITIATIVE_DICE + 1


@pytest.mark.parametrize(
    ("fixture_name", "item_name"),
    [
        ("BLUE.chum5", "Reaction Enhancers"),
        ("SCSi.chum5", "Reaction Enhancers"),
        ("SCSi.chum5", "Wired Reflexes"),
        ("Fuzzy-chargen.chum5", "Wired Reflexes"),
    ],
)
def test_each_fixture_item_is_really_the_sr5_catalog_row_this_wp_models(
    fixture_name: str, item_name: str
) -> None:
    # Guards against the tests above quietly checking a same-named row from another sourcebook:
    # the fixture's `<sourceid>` must be the SR5 catalog id these tests resolve by name.
    root = ET.parse(mundane_fixture_path(fixture_name)).getroot()
    source_ids = {
        item.findtext("sourceid", "")
        for item in root.iter("cyberware")
        if item.findtext("name") == item_name
    }
    assert source_ids == {BY_NAME[item_name].id}


def test_wp81_lets_fuzzys_wired_reflexes_push_reaction_past_its_natural_maximum() -> None:
    """WP81's acceptance case, built from a real fixture's own numbers rather than a synthetic
    character. `Fuzzy-chargen.chum5` buys REA to Human's natural maximum of 6 and installs Wired
    Reflexes Rating 1, which the legacy engine resolves to exactly 6 -- the boundary case the
    docstring of `test_fuzzys_wired_reflexes_match_its_legacy_reaction_total` above already flags.

    That fixture agreed with this engine both before and after WP81 (its natural rating already
    *was* 6), so it proves nothing about the clamp on its own. Buying the *same* implant at
    Rating 3 instead is the one-variable change that separates the two readings: pre-WP81 this
    engine returned 6 (clamped at the natural maximum, silently discarding all 3 points of a
    purchase the player paid nuyen and Essence for); post-WP81 it returns 9, and the natural
    rating the chargen rules read is still 6.
    """
    attributes = _fixture_attributes("Fuzzy-chargen.chum5")
    assert attributes["REA"] == (4, 6)  # 4 points on Human's minimum of 1, plus the implant's +1

    character = _replay("Fuzzy-chargen.chum5", "Human", [("Wired Reflexes", 3)])
    assert character.natural_attribute_value("REA") == 5
    assert character.attribute_value("REA") == 8

    # ... and with the fixture's REA bought all the way to Human's natural maximum, the same
    # Rating 3 implant lands on top of it rather than being swallowed by it.
    at_maximum = _replay_with_points("Human", {"REA": 5}, [("Wired Reflexes", 3)])
    assert at_maximum.natural_attribute_value("REA") == 6
    assert at_maximum.attribute_value("REA") == 9
    # 9 is inside Human's augmented REA maximum of 10, so this is the bonus landing in full, not
    # a second clamp coincidentally producing the same number.
    assert at_maximum.attribute_augmented_maximum("REA") == 10
