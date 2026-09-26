"""WP110: Street Cred, Notoriety and Public Awareness at creation (p. 368)."""

from __future__ import annotations

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.derived import notoriety, public_awareness, street_cred
from chummer5.engine.qualities import (
    QualityPickRequest,
    apply_quality_improvements,
    create_quality_selection,
)

QUALITIES = load_qualities()
BY_NAME = {q.name: q for q in QUALITIES}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _human() -> Character:
    heritage = PRIORITIES.heritage["D"]
    choice = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")
    return create_character(
        metatype_choice=choice,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )


def test_every_p_368_quality_carries_its_notoriety_shift() -> None:
    """The phase file's Finding 3 list, checked against the parsed data -- Gremlins by override."""
    positives = {"Blandness", "First Impression", "Lucky"}
    negatives = {
        "Addiction (Mild)",
        "Addiction (Moderate)",
        "Addiction (Severe)",
        "Addiction (Burnout)",
        "Bad Luck",
        "Combat Paralysis",
        "Elf Poser",
        "Gremlins",
        "Incompetent",
        "Ork Poser",
        "Scorched",
        "SINner (Criminal)",
        "Spirit Bane",
        "Uncouth",
        "Uneducated",
        "Weak Immune System",
    }
    for name in positives:
        assert BY_NAME[name].notoriety == -1, name
    for name in negatives:
        assert BY_NAME[name].notoriety == 1, name
    assert BY_NAME["Bad Rep"].notoriety == 3
    listed = positives | negatives | {"Bad Rep"}
    assert {q.name for q in QUALITIES if q.notoriety} == listed


def test_sinner_criminal_and_bad_rep_give_notoriety_4() -> None:
    character = _human()
    selection = create_quality_selection(
        [QualityPickRequest(BY_NAME["SINner (Criminal)"].id, text="Lone Star priors")], QUALITIES
    )
    apply_quality_improvements(character, selection.qualities)
    apply_quality_improvements(character, [BY_NAME["Bad Rep"]])
    assert notoriety(character) == 4


def test_positive_qualities_lower_notoriety_below_zero() -> None:
    character = _human()
    apply_quality_improvements(character, [BY_NAME["Blandness"], BY_NAME["Lucky"]])
    assert notoriety(character) == -2


def test_two_addictions_count_once() -> None:
    """p. 368 lists "Addiction", and a character "cannot earn a Notoriety point for something for
    which they have already received a point"."""
    character = _human()
    apply_quality_improvements(
        character, [BY_NAME["Addiction (Mild)"], BY_NAME["Addiction (Severe)"], BY_NAME["Bad Luck"]]
    )
    assert notoriety(character) == 2


def test_street_cred_and_public_awareness_are_zero_at_creation() -> None:
    character = _human()
    apply_quality_improvements(character, [BY_NAME["Bad Rep"]])
    assert street_cred(character) == 0
    assert public_awareness(character) == 0
