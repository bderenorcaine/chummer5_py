"""Regression tests over the synthetic whole-character fixtures (Phase S / WP72+).

These cover subsystem *interactions* the fixed `.chum5` corpus structurally can't (only one mundane
Priority fixture exists) — see `tests/fixtures/synthetic.py`'s module docstring. Each fixture is
built through the real engine and every hand-derived `expected` value asserted, with each asserted
metric required to carry a citation (`assert_fixture` enforces both).
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from tests.fixtures.native_saves import RAZORBOY_SAVE, native_save_path
from tests.fixtures.synthetic import (
    CyberwareEntryPick,
    CyberwarePick,
    SyntheticCharacter,
    assert_fixture,
    build_synthetic,
    cyberware_purchase_request,
    resolve_metric,
)
from tests.fixtures.synthetic_fixtures import (
    COMBAT_MAGE_FIXTURE,
    DECKER_FIXTURE,
    REFERENCE_MUNDANE_FIXTURE,
    SHAMAN_FACE_FIXTURE,
    STREET_SAMURAI_FIXTURE,
    SYNTHETIC_FIXTURES,
)

from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.build_method import (
    PRIORITY_BUILD_METHOD,
    SUM_TO_TEN_BUILD_METHOD,
    SUM_TO_TEN_TARGET,
    sum_to_ten_total,
)
from chummer5.engine.knowledge import KnowledgeSkillPick, LanguageSkillPick
from chummer5.engine.resources import Contact
from chummer5.io.save_format import build_character, from_json


@pytest.mark.parametrize("fixture", SYNTHETIC_FIXTURES, ids=lambda f: f.name)
def test_synthetic_fixture_matches_hand_derived_values(fixture) -> None:  # type: ignore[no-untyped-def]
    assert_fixture(fixture)


def test_reference_fixture_builds_a_finalized_character() -> None:
    """The reference mundane-Priority build produces a `Character` carrying the committed
    skill/quality selections the harness fed it — a smoke check that `build_synthetic` wires the
    real engine's public API end to end, not just that the numbers happen to match.
    """
    character = build_synthetic(REFERENCE_MUNDANE_FIXTURE)
    assert character.metatype.name == "Human"
    assert character.skill_allocation is not None
    assert character.quality_selection is not None
    # Catlike's +2 Sneaking improvement actually landed in the ImprovementIndex.
    assert resolve_metric(character, "rating:Sneaking") == 5


def test_street_samurai_stacks_cyberware_and_bioware_essence() -> None:
    """The WP73 samurai commits both a cyberware and a bioware selection, and the two Essence costs
    stack against the one shared pool — the interaction (G1/G2) no `.chum5` fixture exercises. A
    smoke check that `build_synthetic` wires both selection functions through the real engine in the
    documented cyberware-first/bioware-second order, not just that the derived numbers happen to
    match.
    """
    character = build_synthetic(STREET_SAMURAI_FIXTURE)
    assert character.metatype.name == "Ork"
    assert character.cyberware_selection is not None
    assert character.bioware_selection is not None
    # Both sources contribute to one Essence pool: 6 - 3.1 - 0.5 = 2.4.
    assert character.cyberware_selection.essence_spent == Decimal("3.1")
    assert character.bioware_selection.essence_spent == Decimal("0.5")
    assert resolve_metric(character, "essence") == Decimal("2.4")
    # The Enhanced Articulation bioware bonus reached the Escape Artist rating (1 bought + 1 bio).
    assert resolve_metric(character, "rating:Escape Artist") == 2


def test_combat_mage_essence_loss_reduces_magic_and_carries_foci_and_mentor() -> None:
    """The WP74 combat mage is a magician whose cyberware Essence loss drops her Magic rating, who
    also carries a bonded focus and a mentor spirit — the interactions (G3/G6) no `.chum5` fixture
    exercises (the corpus's two magic Priority builds carry zero cyberware). A smoke check that
    `build_synthetic` wires the magic/cyberware/foci/mentor paths through the real engine, and that
    the Essence→Magic loss actually flows into the downstream caps and MAG-linked dice pools, not
    just the headline rating.
    """
    character = build_synthetic(COMBAT_MAGE_FIXTURE)
    assert character.metatype.name == "Human"
    assert character.magic_type == "Magician"
    assert character.cyberware_selection is not None
    assert character.foci_selection is not None
    assert character.quality_selection is not None
    assert character.quality_selection.mentor_spirit is not None

    # G3: a 0.3 Essence loss (< 1 point) still costs a full Magic point (6 -> 5).
    assert character.magic_rating_before_essence_loss == 6
    assert character.magic_essence_loss == 1
    assert resolve_metric(character, "essence") == Decimal("5.7")
    assert character.attribute_value("MAG") == 5
    # The reduced MAG flows into a MAG-linked skill's dice pool, not just the raw rating.
    assert resolve_metric(character, "pool:Spellcasting") == 10  # rating 5 + reduced MAG 5

    # G6: the mentor's General (+2 Survival) and Magician (+2 Counterspelling) FLAT_BONUS slots
    # both landed as Improvements; Counterspelling's grant (5) + mentor (2) caps at 6.
    assert resolve_metric(character, "rating:Survival") == 4  # 2 bought + 2 Mountain General
    # WP82: 7, not 6. The Talent grant (5) and the Mountain mentor's Magician slot (+2) are both
    # Improvements, and SR5's 6 caps what may be *bought* (p. 131) -- so neither is bounded by it.
    assert resolve_metric(character, "rating:Counterspelling") == 7
    # The bonded Power Focus committed its nuyen/Karma cost.
    assert character.foci_selection.karma_cost == 12


def test_shaman_face_spends_leftover_karma_breaking_a_group_and_buying_a_spell() -> None:
    """The WP75 shaman face spends every point of her Step Seven leftover Karma — on an attribute,
    on an individual skill raise that *breaks* a purchased skill group, on a Karma-funded
    specialization, on raising a second group as a group, and on a spell beyond her free Talent
    budget — the interactions (G4/G5) no `.chum5` fixture exercises at all (`learnings/phase-o.md`'s
    WP53/WP54 entries both record "no fixture ... hand-verified"). A smoke check that
    `build_synthetic` drives the real Step Seven selection functions in the documented
    attributes→skills→spells order, and that the group-breaking split reaches the affected ratings
    rather than only the Karma ledger.
    """
    character = build_synthetic(SHAMAN_FACE_FIXTURE)
    assert character.metatype.name == "Elf"
    assert character.magic_type == "Magician"
    assert character.karma_attribute_selection is not None
    assert character.karma_skill_selection is not None
    assert character.spell_selection is not None

    # G4: only Influence broke, and only Negotiation left it — its siblings keep the group rating.
    assert character.karma_skill_selection.broken_groups == frozenset({"Influence"})
    assert resolve_metric(character, "rating:Negotiation") == 5
    assert resolve_metric(character, "rating:Etiquette") == 4
    # The Karma-funded specialization reaches the dice pool (+2), on top of the broken-out rating.
    assert resolve_metric(character, "pool:Negotiation") == 15  # 5 + CHA 8 + 2 spec
    # Conjuring was raised *as a group* with Karma instead — 1 priority point + 1 Karma point.
    assert resolve_metric(character, "rating:Binding") == 2

    # G5: the 6th spell is Karma-funded, at exactly the Magic 3 x 2 known-spells cap.
    assert len(character.spell_selection.spells) == 6
    assert character.spell_selection.budget == 5
    assert character.spell_selection.karma_spell_count == 1

    # The whole 25-Karma pool (widened to 42 by net-negative qualities) is spent to the point.
    assert character.karma_spent == 25
    assert character.karma_remaining == 0


def test_decker_is_a_sum_to_ten_build_illegal_under_priority() -> None:
    """The WP76 decker is the first synthetic fixture built with the **Sum-to-Ten**
    letter-assignment rule instead of Priority's bijection — the interaction (G7) no `.chum5`
    fixture exercises through this engine (33 of the 34 legacy fixtures are `SumtoTen`-built, but
    WP4 only reads their finished values; none is ever validated or rebuilt here). Pins down both
    halves of what "a different build method" means: the five letters total exactly
    `SUM_TO_TEN_TARGET`, and the *same* five letters are rejected outright under
    `PRIORITY_BUILD_METHOD` because two of them repeat.
    """
    letters = (
        DECKER_FIXTURE.heritage_letter,
        DECKER_FIXTURE.attributes_letter,
        DECKER_FIXTURE.skills_letter,
        DECKER_FIXTURE.resources_letter,
        "E",  # Talent, left unset (mundane) — worth 0 Sum-to-Ten points
    )
    assert DECKER_FIXTURE.build_method == SUM_TO_TEN_BUILD_METHOD
    assert sum_to_ten_total(letters) == SUM_TO_TEN_TARGET
    # Repeats are exactly what Priority forbids and Sum-to-Ten allows.
    assert len(set(letters)) < len(letters)
    with pytest.raises(ValueError):
        build_synthetic(replace(DECKER_FIXTURE, build_method=PRIORITY_BUILD_METHOD))

    # The layered cyberware and the Step Seven spend still land on top of the Sum-to-Ten budgets.
    character = build_synthetic(DECKER_FIXTURE)
    assert character.metatype.name == "Dwarf"
    assert character.cyberware_selection is not None
    assert resolve_metric(character, "essence") == Decimal("5.3")
    # A Karma specialization on a skill whose group was never group-bought breaks nothing — the
    # complement of WP75's group-breaking case.
    assert character.karma_skill_selection is not None
    assert character.karma_skill_selection.broken_groups == frozenset()
    assert resolve_metric(character, "pool:Hacking") == 14  # 6 + LOG 6 + 2 spec


def test_unsupported_build_method_raises() -> None:
    """An unrecognised `build_method` is rejected rather than silently falling back to either real
    rule — mirroring `submit_priorities`, which itemises it as its own error.
    """
    with pytest.raises(ValueError, match="unsupported build method"):
        build_synthetic(replace(DECKER_FIXTURE, build_method="Karma"))


def test_unrecognised_metric_key_raises() -> None:
    character = build_synthetic(REFERENCE_MUNDANE_FIXTURE)
    with pytest.raises(KeyError):
        resolve_metric(character, "not:a:metric")


# The cyberware tree `tests/fixtures/saves/razorboy.json` carries, re-expressed in WP86's widened
# authoring shape: two rated parents with four plugins each (their bundled Sound Link / Image Link
# deliberately absent — the engine installs those), three flat implants, and one rated standalone.
# WP88 authors the whole character as a `SyntheticCharacter`; this constant is the narrow proof that
# the *field* can say what the save file says, landed before the fixture that depends on it.
RAZORBOY_CYBERWARE: tuple[CyberwareEntryPick, ...] = (
    "Bone Lacing (Titanium)",
    CyberwarePick("Wired Reflexes", rating=2),
    "Hand Blade",
    "Shock Hand",
    CyberwarePick(
        "Cyberears",
        rating=3,
        plugins=(
            CyberwarePick("Audio Enhancement", rating=3),
            "Balance Augmenter",
            CyberwarePick("Select Sound Filter", rating=3),
            "Spatial Recognizer",
        ),
    ),
    CyberwarePick(
        "Cybereyes Basic System",
        rating=3,
        plugins=(
            "Flare Compensation",
            "Low-Light Vision",
            "Ocular Drone",
            CyberwarePick("Vision Enhancement", rating=3),
        ),
    ),
    "Datajack",
)


def test_cyberware_picks_express_a_real_save_file_exactly() -> None:
    """WP86's acceptance criterion: the widened `cyberware` field can express `razorboy.json`'s
    `cyberware_purchases` *exactly*.

    Asserted as structural equality against the save's own request tree, not merely as matching
    totals — two different trees can coincidentally cost the same, and it's the tree shape (which
    plugin sits in which parent, at what rating) that WP38/WP41/WP42 built and that WP73-76's flat
    name list could not say at all.
    """
    save = from_json(native_save_path(RAZORBOY_SAVE).read_text(encoding="utf-8"))
    assert [cyberware_purchase_request(pick) for pick in RAZORBOY_CYBERWARE] == list(
        save.cyberware_purchases
    )


def test_cyberware_picks_reproduce_the_saves_essence_nuyen_and_capacity() -> None:
    """The same tree, resolved through `build_synthetic()`, produces the save's own Essence, nuyen
    and per-parent Capacity figures — so the harness and the real load path agree on what this
    purchase costs, not just on how it's spelled.

    The synthetic side is given a Resources letter with enough nuyen to carry the ¥260,000 tree on
    its own (the save also spends on gear, Lifestyle and Rating-priced gear, which WP87 adds and
    this WP deliberately doesn't), so the comparison is cyberware-to-cyberware.
    """
    fixture = replace(DECKER_FIXTURE, cyberware=RAZORBOY_CYBERWARE, resources_letter="A")
    # Sum-to-Ten totals shift when a letter changes; restore the exact-10 sum via Attributes.
    fixture = replace(fixture, attributes_letter="E", attribute_points={})
    character = build_synthetic(fixture)

    assert character.cyberware_selection is not None
    assert character.cyberware_selection.essence_spent == Decimal("5.90")
    assert character.cyberware_selection.nuyen_spent == 260000
    for parent in ("Cyberears", "Cybereyes Basic System"):
        assert resolve_metric(character, f"cyberware:{parent}:capacity_budget") == Decimal(12)
        assert resolve_metric(character, f"cyberware:{parent}:capacity_spent") == Decimal(12)
        assert resolve_metric(character, f"cyberware:{parent}:capacity_remaining") == Decimal(0)
    # A plugin's own charge against its parent, addressed through the same path grammar.
    assert resolve_metric(
        character, "cyberware:Cybereyes Basic System/Ocular Drone:capacity_cost"
    ) == Decimal(6)


def test_declaring_a_bundled_subsystem_is_an_error() -> None:
    """Cyberears bundles Sound Link free; naming it as a plugin would buy a second, paid copy and
    silently inflate the nuyen and Capacity totals a fixture exists to pin down. Rejected at
    authoring time rather than resolved into a duplicate.
    """
    with pytest.raises(ValueError, match="bundled free"):
        cyberware_purchase_request(CyberwarePick("Cyberears", rating=3, plugins=("Sound Link",)))


# `razorboy.json`'s own spend side, re-expressed in WP87's widened authoring fields. WP88 authors
# the whole character; this is the narrow proof that the *fields* can say what the save says, landed
# before the fixture that depends on them.
RAZORBOY_GEAR = (
    "Ammo: Gel Rounds",
    "Ammo: Regular Ammo",
    "Armor Jacket",
    "Ares Alpha",
    "Hermes Ikon",
    "Ares Predator V",
)
RAZORBOY_KNOWLEDGE = (
    KnowledgeSkillPick(name="Trivia Games", category="Interest", rating=3),
    KnowledgeSkillPick(name="Combat Tactics", category="Professional", rating=3),
    KnowledgeSkillPick(name="Underground Fight Scene", category="Interest", rating=3),
    KnowledgeSkillPick(name="Area Knowledge (Seattle)", category="Street", rating=3),
)


def _razorboy_spend_side() -> SyntheticCharacter:
    """A Sum-to-Ten fixture carrying razorboy.json's exact priorities, attributes and spend side.

    Deliberately *not* the whole character — the skills, qualities and cyberware are WP88's job.
    What this pins down is that the new fields, wired in `build_character`'s own order, reproduce
    the same budget arithmetic the real load path does off the same inputs.
    """
    return SyntheticCharacter(
        name="razorboy spend-side (WP87)",
        metatype="Human",
        heritage_letter="E",
        attributes_letter="B",
        skills_letter="A",
        resources_letter="B",
        build_method=SUM_TO_TEN_BUILD_METHOD,
        attribute_points={
            "BOD": 2,
            "AGI": 3,
            "REA": 3,
            "STR": 4,
            "CHA": 2,
            "INT": 3,
            "LOG": 1,
            "WIL": 2,
            "EDG": 1,
        },
        gear=RAZORBOY_GEAR,
        rating_gear=(("Fake SIN", 4),),
        lifestyle=("Medium", 1),
        karma_converted=4,
        cyberware=RAZORBOY_CYBERWARE,
        contacts=(
            Contact(name="Heterodyne", connection=4, loyalty=1),
            Contact(name="Stitch", connection=4, loyalty=3),
        ),
        knowledge_skills=RAZORBOY_KNOWLEDGE,
        languages=(LanguageSkillPick(name="English", rating=0, native=True),),
        expected={},
        citations={},
    )


def test_spend_side_fields_reproduce_the_saves_nuyen_and_knowledge_budgets() -> None:
    """WP87's acceptance criterion: the new fields reproduce `razorboy.json`'s ¥580 remaining and
    its 12/12 Knowledge points.

    Asserted against the save's *own* rebuilt character, not against transcribed constants — if the
    harness and `build_character` ever disagree about the evaluation order or which budget a cost
    lands in, this fails, which is the whole point of following that function's order rather than
    inventing one.
    """
    save = from_json(native_save_path(RAZORBOY_SAVE).read_text(encoding="utf-8"))
    from_save = build_character(
        save,
        metatypes=load_metatypes(),
        priorities=load_priorities(),
        skills=load_skills(),
        qualities=load_qualities(),
        lifestyles=load_lifestyles(),
        cyberware=load_cyberware_entries(),
    )
    character = build_synthetic(_razorboy_spend_side())

    # ¥275,000 from Resources B, topped up to ¥283,000 by converting 4 Karma; ¥580 survives gear,
    # Rating-priced gear, a month of Medium Lifestyle and ¥260,000 of chrome.
    assert resolve_metric(character, "nuyen:budget") == 275000
    assert resolve_metric(character, "nuyen:available") == 283000
    assert resolve_metric(character, "nuyen:lifestyle_cost") == 5000
    assert resolve_metric(character, "nuyen:remaining") == 580
    assert from_save.resources_selection is not None
    assert (
        resolve_metric(character, "nuyen:remaining")
        == from_save.resources_selection.nuyen_remaining
    )

    # (natural INT 4 + natural LOG 2) x 2 = 12, spent to the pin on four Rating-3 Knowledge skills;
    # the native language is free and doesn't count against it (p. 95).
    assert resolve_metric(character, "knowledge:free_points") == 12
    assert resolve_metric(character, "knowledge:points_spent") == 12
    assert resolve_metric(character, "knowledge:native_language_limit") == 1
    assert from_save.knowledge_selection is not None
    assert (
        resolve_metric(character, "knowledge:free_points")
        == from_save.knowledge_selection.free_points
    )

    # natural CHA 3 x 3 = 9 free contact points; 5 + 7 = 12 spent, so 3 excess at 1 Karma each.
    assert resolve_metric(character, "contacts:free_points") == 9
    assert resolve_metric(character, "contacts:points_spent") == 12
    assert resolve_metric(character, "contacts:karma_cost") == 3

    # Knowledge dice pools: Interest/Street link to INT, Academic/Professional to LOG (p. 89).
    assert resolve_metric(character, "knowledge:pool:Trivia Games") == 7  # 3 + INT 4
    assert resolve_metric(character, "knowledge:pool:Combat Tactics") == 5  # 3 + LOG 2


def test_native_language_has_no_dice_pool() -> None:
    """A native pick carries fluency "N", not a rating, so asking for its pool is an error rather
    than a silently wrong `0 + INT`."""
    character = build_synthetic(_razorboy_spend_side())
    with pytest.raises(KeyError, match="native language"):
        resolve_metric(character, "languages:pool:English")
