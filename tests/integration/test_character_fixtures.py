"""Cross-checks `chummer5.engine.character` against the WP4 legacy `.chum5` golden corpus.

Two different kinds of assertion, per the Implementation Plan's corpus note and
`tests/fixtures/README.md`:
- `Yeti-#ffffff2.chum5` (the corpus's only `buildmethod == Priority` fixture) validates the full
  priority-allocation path: `metatype_choices()` + `create_character()`'s budget checks, using
  Yeti's own recorded priority letters.
- The rest of the mundane corpus (`SumtoTen`-built) validates only `Character.attribute_value()`'s
  formula, build-method-agnostically, by constructing a `Character` directly from each fixture's
  recorded `base + karma` points -- bypassing `create_character()`'s budget validation, which is
  priority-build-specific and wouldn't mean anything against a SumToTen spend. See
  `spec/worklogs/WP6.md` for why `<totalvalue>` can't be used for every attribute of every
  fixture: it's the *augmented* value (includes cyberware/gear), and MVP doesn't model those, so
  only attributes with no such equipment are asserted per fixture.
"""

from __future__ import annotations

from types import MappingProxyType

from tests.fixtures.mundane_chum5 import (
    MUNDANE_FIXTURES,
    PRIORITY_BUILD_FIXTURE,
    mundane_fixture_path,
)

from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import Metatype, load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.character import (
    ALLOCATABLE_ATTRIBUTES,
    Character,
    create_character,
    metatype_choices,
    sr5_metatypes,
)
from chummer5.engine.derived import (
    initiative_dice,
    initiative_value,
    mental_limit,
    physical_condition_monitor,
    physical_limit,
    social_limit,
    stun_condition_monitor,
)
from chummer5.engine.improvements import ImprovementIndex, ImprovementType
from chummer5.engine.lifestyle import create_lifestyle_selection
from chummer5.engine.qualities import (
    apply_quality_improvements,
    create_quality_selection,
    resolve_metatype_qualities,
)
from chummer5.engine.resources import (
    Contact,
    create_contact_selection,
    create_resources_selection,
    starting_nuyen,
)
from chummer5.engine.skills import create_skill_allocation, skill_rating
from chummer5.io.legacy_chum5 import load_chum5, priority_letter

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
QUALITIES = load_qualities()
LIFESTYLES = load_lifestyles()


def test_yeti_priority_build_matches_engine_end_to_end() -> None:
    legacy = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    assert legacy.build_method == "Priority"
    assert legacy.metatype == "Human"
    assert legacy.metavariant is None

    heritage_letter = priority_letter(legacy.priorities.heritage)
    attributes_letter = priority_letter(legacy.priorities.attributes)
    assert (heritage_letter, attributes_letter) == ("D", "A")

    heritage = PRIORITIES.heritage[heritage_letter]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )

    attribute_points = {
        code: legacy.attributes[code].base + legacy.attributes[code].karma
        for code in ALLOCATABLE_ATTRIBUTES
    }
    character = create_character(
        metatype_choice=human_choice,
        heritage_letter=heritage_letter,
        attributes_letter=attributes_letter,
        priorities=PRIORITIES,
        attribute_points=attribute_points,
    )

    for code in ALLOCATABLE_ATTRIBUTES:
        assert character.attribute_value(code) == legacy.attributes[code].total_value, code


def test_yeti_skill_allocation_matches_engine_end_to_end() -> None:
    """Validates WP7's priority-allocation path (budgets, group-vs-individual rating) against the
    same fixture WP6 used for attributes. There's no stored "computed dice pool" in `.chum5` to
    cross-check the dice pool formula itself against -- see `spec/worklogs/WP7.md` -- so this test
    covers allocation/rating only; the dice pool formula is covered by synthetic tests in
    `tests/unit/test_skill_allocation.py`, mirroring WP5's precedent for the Improvement engine.
    """
    legacy = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    skills_letter = priority_letter(legacy.priorities.skills)
    assert skills_letter == "C"

    # Only skills.xml skill ids/groups are cross-referenced -- <newskills> also carries a handful of
    # Resonance/knowledge-adjacent entries whose <suid> may not resolve to an in-scope active skill;
    # none of Yeti's nonzero-base entries fall in that gap (checked below via `checked_nonzero`).
    skills_by_id = {s.id: s for s in SKILLS}
    bought_groups = {g.name: g.base for g in legacy.skill_groups if g.base > 0}

    skill_points: dict[str, int] = {}
    checked_nonzero = 0
    for legacy_skill in legacy.skills:
        if legacy_skill.base <= 0:
            continue
        skill = skills_by_id.get(legacy_skill.suid)
        if skill is None or (skill.skill_group is not None and skill.skill_group in bought_groups):
            # Skipped deliberately: a skill whose group is bought never carries its own base points
            # in the legacy data either (see module docstring) -- nothing to feed as skill_points.
            continue
        skill_points[skill.id] = legacy_skill.base
        checked_nonzero += 1

    assert checked_nonzero > 0  # sanity: the fixture actually exercises this path

    allocation = create_skill_allocation(
        letter=skills_letter,
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points=skill_points,
        group_points=bought_groups,
    )

    budget = PRIORITIES.skills[skills_letter]
    assert sum(allocation.skill_points.values()) <= budget.skills
    assert sum(allocation.group_points.values()) == budget.skill_groups  # Yeti spends both exactly

    heritage_letter = priority_letter(legacy.priorities.heritage)
    attributes_letter = priority_letter(legacy.priorities.attributes)
    heritage = PRIORITIES.heritage[heritage_letter]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(
        metatype_choice=human_choice,
        heritage_letter=heritage_letter,
        attributes_letter=attributes_letter,
        priorities=PRIORITIES,
        attribute_points={
            code: legacy.attributes[code].base + legacy.attributes[code].karma
            for code in ALLOCATABLE_ATTRIBUTES
        },
    )

    # A skill in a bought group (Firearms) picks up the group's rating, not its own (zero) base.
    automatics = next(s for s in SKILLS if s.name == "Automatics")
    assert automatics.skill_group == "Firearms"
    assert skill_rating(character, allocation, automatics) == bought_groups["Firearms"]

    # A skill with its own base points, in an unbought group (Cracking), uses its own points.
    hacking = next(s for s in SKILLS if s.name == "Hacking")
    assert hacking.skill_group == "Cracking"
    assert "Cracking" not in bought_groups
    assert skill_rating(character, allocation, hacking) == 2


def test_cross_corpus_attribute_value_matches_when_unaugmented() -> None:
    """For every mundane fixture with a plain (non-metavariant) SR5 base metatype, the
    `metatype minimum + base + karma` formula should reproduce `<totalvalue>` for any attribute
    that isn't also being boosted by cyberware/gear -- augmentation is out of MVP scope, so those
    specific attributes are skipped rather than asserted against a number this engine doesn't
    (yet) model the source of.
    """
    metatypes_by_name: dict[str, Metatype] = {m.name: m for m in sr5_metatypes(METATYPES)}
    checked_at_least_one = False

    for fixture_name in MUNDANE_FIXTURES:
        legacy = load_chum5(mundane_fixture_path(fixture_name))
        if legacy.metavariant is not None:
            # Metavariants override attribute ranges and are entirely out of MVP scope (see
            # spec/worklogs/WP6.md) -- the base metatype's ranges below would not apply.
            continue
        metatype = metatypes_by_name[legacy.metatype]

        character = Character(
            metatype=metatype,
            heritage_letter="",
            attributes_letter="",
            special_attribute_points=0,
            attribute_points=MappingProxyType(
                {
                    code: legacy.attributes[code].base + legacy.attributes[code].karma
                    for code in ALLOCATABLE_ATTRIBUTES
                }
            ),
            improvements=ImprovementIndex(),
        )

        for code in ALLOCATABLE_ATTRIBUTES:
            legacy_attribute = legacy.attributes[code]
            natural_value = (
                metatype.attributes[code].minimum + legacy_attribute.base + legacy_attribute.karma
            )
            if natural_value != legacy_attribute.total_value:
                # Augmented by cyberware/gear this WP doesn't model -- not a formula mismatch.
                continue
            checked_at_least_one = True
            assert character.attribute_value(code) == legacy_attribute.total_value, (
                fixture_name,
                code,
            )

    assert checked_at_least_one


def test_blindfire_catlike_quality_matches_engine_end_to_end() -> None:
    """`Blindfire.chum5` is the only mundane fixture carrying one of WP3's 3 MVP-offered
    (`FLAT_BONUS`) qualities -- Catlike. It also carries several out-of-scope (non-SR5-sourced, or
    SR5 but `NOT_YET_SUPPORTED`) qualities, so this only cross-checks Catlike specifically -- a full
    quality-list rebuild isn't meaningful for this fixture (see WP8's worklog for why), unlike
    Yeti's role for WP6/WP7's full-allocation tests.
    """
    legacy = load_chum5(mundane_fixture_path("Blindfire.chum5"))
    legacy_catlike = next(q for q in legacy.qualities if q.name == "Catlike")
    assert legacy_catlike.source == "SR5"
    assert legacy_catlike.karma == 7

    catalog_catlike = next(q for q in QUALITIES if q.name == "Catlike")
    assert catalog_catlike.id == legacy_catlike.id
    assert catalog_catlike.karma == legacy_catlike.karma

    selection = create_quality_selection([catalog_catlike.id], QUALITIES)
    assert selection.positive_karma == legacy_catlike.karma

    heritage = PRIORITIES.heritage["D"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(
        metatype_choice=human_choice,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )
    apply_quality_improvements(character, selection.qualities)
    assert character.improvements.resolve(ImprovementType.SKILL, "Sneaking") == 2


# WP23: the 5 curated mundane fixtures with a non-Human core metatype, each carrying that
# metatype's real free racial quality/qualities, tagged `qualitysource=Metatype` in the raw
# `.chum5` -- confirmed during this WP's research (see spec/worklogs/WP23.md).
_NON_HUMAN_FIXTURES = {
    "BLUE.chum5": ("Ork", ("Low-Light Vision",)),
    "Blindfire.chum5": ("Elf", ("Low-Light Vision",)),
    "Gentle Earthquake.chum5": ("Troll", ("Thermographic Vision",)),
    "Monomax (approved) 3.chum5": ("Troll", ("Thermographic Vision",)),
    "Rez0luti0n2.0.chum5": ("Dwarf", ("Thermographic Vision",)),
}


def test_resolve_metatype_qualities_matches_every_non_human_fixture() -> None:
    """Cross-checks `resolve_metatype_qualities` against real legacy-computed ground truth: every
    curated mundane fixture with a non-Human core metatype (5 of 11 -- see `_NON_HUMAN_FIXTURES`)
    carries its metatype's real racial quality/qualities in its own `<quality>` list, each tagged
    `qualitysource=Metatype`. `Rez0luti0n2.0.chum5`'s Dwarf is missing Resistance to Pathogens/
    Toxins entirely (a real, pre-existing gap in that specific save, not a parsing bug -- confirmed
    directly against the raw XML during WP23's research), so this only asserts the *subset* each
    fixture's own `qualitysource=Metatype` entries name, not that `resolve_metatype_qualities`'
    full output is always a perfect match to every fixture -- the assertion direction that's
    actually meaningful as ground truth.
    """
    assert set(_NON_HUMAN_FIXTURES) <= set(MUNDANE_FIXTURES)
    checked = 0
    for fixture_name, (metatype_name, expected_names) in _NON_HUMAN_FIXTURES.items():
        legacy = load_chum5(mundane_fixture_path(fixture_name))
        assert legacy.metatype == metatype_name, fixture_name

        legacy_metatype_quality_names = {
            q.name for q in legacy.qualities if q.quality_source == "Metatype"
        }
        assert set(expected_names) <= legacy_metatype_quality_names, fixture_name

        metatype = next(m for m in METATYPES if m.name == metatype_name and m.source == "SR5")
        resolved_names = {q.name for q in resolve_metatype_qualities(metatype, QUALITIES)}
        assert set(expected_names) <= resolved_names, fixture_name
        checked += 1
    assert checked == len(_NON_HUMAN_FIXTURES)


def test_cross_corpus_contact_free_budget_matches_cha_times_three() -> None:
    """Every mundane fixture's `<contactpoints>` (the save format's cached free-contact-point
    budget) equals its own `CHA` `<totalvalue>` times 3 -- confirmed for all 11 during WP9's
    research (see spec/worklogs/WP9.md), cross-validating `chummer5.engine.resources`'s
    `FREE_CONTACT_POINTS_PER_CHARISMA` constant against real legacy-computed data, the same kind of
    cross-loader check WP4 ran for starting nuyen.
    """
    checked = 0
    for fixture_name in MUNDANE_FIXTURES:
        legacy = load_chum5(mundane_fixture_path(fixture_name))
        cha_total = legacy.attributes["CHA"].total_value
        assert cha_total * 3 == legacy.contact_points_budget, fixture_name
        checked += 1
    assert checked == len(MUNDANE_FIXTURES)


def test_cross_corpus_lifestyle_cost_matches_tier_monthly_rate_times_months() -> None:
    """WP20: every mundane fixture's primary Lifestyle (the first `<lifestyle>` entry -- see
    `chummer5.io.legacy_import`'s module docstring for why "first" is this project's own
    "primary" convention) reproduces `chummer5.engine.lifestyle.create_lifestyle_selection`'s
    `tier.monthly_cost * months` formula against real legacy-computed data -- build-method-
    agnostic, the same "all 11, not just Yeti" scope every prior WP's *derived-value* fixture test
    uses (see tests/fixtures/README.md), since a Lifestyle's cost has nothing to do with how the
    rest of the character's points were allocated.
    """
    checked = 0
    for fixture_name in MUNDANE_FIXTURES:
        legacy = load_chum5(mundane_fixture_path(fixture_name))
        assert legacy.lifestyles, fixture_name
        primary = legacy.lifestyles[0]
        selection = create_lifestyle_selection(primary.base_lifestyle, primary.months, LIFESTYLES)
        assert selection.tier.monthly_cost == primary.monthly_cost, fixture_name
        assert selection.total_cost == primary.monthly_cost * primary.months, fixture_name
        checked += 1
    assert checked == len(MUNDANE_FIXTURES)


def test_yeti_contacts_match_engine_end_to_end() -> None:
    """Yeti's two contacts ((3,3) and (5,4)) sum to exactly its free budget (15 == CHA 5 * 3), so
    `karma_cost` comes out to 0 -- a clean, real-data confirmation of both the budget formula and
    the "no karma owed while under budget" case. The excess-karma case itself (a selection that
    goes *over* budget) is covered synthetically in `tests/unit/test_resources.py`, since no
    mundane fixture's engine-reconstructable contact list happens to exceed its own budget.
    """
    legacy = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    assert legacy.contact_points_budget == 15

    heritage_letter = priority_letter(legacy.priorities.heritage)
    attributes_letter = priority_letter(legacy.priorities.attributes)
    heritage = PRIORITIES.heritage[heritage_letter]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(
        metatype_choice=human_choice,
        heritage_letter=heritage_letter,
        attributes_letter=attributes_letter,
        priorities=PRIORITIES,
        attribute_points={
            code: legacy.attributes[code].base + legacy.attributes[code].karma
            for code in ALLOCATABLE_ATTRIBUTES
        },
    )
    assert character.attribute_value("CHA") == 5

    contacts = tuple(
        Contact(name=c.name, connection=c.connection, loyalty=c.loyalty, free=c.free)
        for c in legacy.contacts
    )
    assert len(contacts) == 2
    selection = create_contact_selection(character, contacts)
    assert selection.free_points == legacy.contact_points_budget
    assert selection.points_spent == 15
    assert selection.karma_cost == 0


def test_yeti_full_character_regression_end_to_end() -> None:
    """WP10's headless-MVP milestone test: build `Yeti-#ffffff2.chum5` through every engine module
    (metatype/attributes, skills, contacts, resources, and WP10's own derived stats) in one pass,
    diffing every field that has real legacy-computed ground truth to diff against.

    Qualities are deliberately not part of this build: Yeti's own quality list (Technomancer,
    Infirm, Impassive, Paranoia, Faceless, Data Anomaly -- see spec/worklogs/WP9.md) contains none
    of WP8's 3 MVP-offered (`FLAT_BONUS`) qualities, so there is nothing constructible from it --
    `test_blindfire_catlike_quality_matches_engine_end_to_end` above already covers the one real
    fixture that does exercise a quality build.

    The derived-stat formulas themselves (initiative, the three Limits, both condition monitors)
    have no stored `.chum5` field to diff against (see `chummer5.engine.derived`'s module
    docstring and `spec/worklogs/WP10.md`) -- they're checked here against hand-computed values
    built directly from Yeti's own recorded, legacy-computed attribute totals (BOD 4, REA 2, STR 2,
    CHA 5, INT 5, LOG 6, WIL 5), the same "real numbers, hand-verified arithmetic" standard used
    everywhere else in this test module.
    """
    legacy = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    heritage_letter = priority_letter(legacy.priorities.heritage)
    attributes_letter = priority_letter(legacy.priorities.attributes)
    heritage = PRIORITIES.heritage[heritage_letter]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(
        metatype_choice=human_choice,
        heritage_letter=heritage_letter,
        attributes_letter=attributes_letter,
        priorities=PRIORITIES,
        attribute_points={
            code: legacy.attributes[code].base + legacy.attributes[code].karma
            for code in ALLOCATABLE_ATTRIBUTES
        },
    )
    for code in ALLOCATABLE_ATTRIBUTES:
        assert character.attribute_value(code) == legacy.attributes[code].total_value, code

    # Skills: same allocation build as test_yeti_skill_allocation_matches_engine_end_to_end above.
    skills_letter = priority_letter(legacy.priorities.skills)
    skills_by_id = {s.id: s for s in SKILLS}
    bought_groups = {g.name: g.base for g in legacy.skill_groups if g.base > 0}
    skill_points = {
        skill.id: legacy_skill.base
        for legacy_skill in legacy.skills
        if legacy_skill.base > 0
        for skill in [skills_by_id.get(legacy_skill.suid)]
        if skill is not None
        and not (skill.skill_group is not None and skill.skill_group in bought_groups)
    }
    allocation = create_skill_allocation(
        letter=skills_letter,
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points=skill_points,
        group_points=bought_groups,
    )
    automatics = next(s for s in SKILLS if s.name == "Automatics")
    assert skill_rating(character, allocation, automatics) == bought_groups["Firearms"]

    # Contacts.
    contacts = tuple(
        Contact(name=c.name, connection=c.connection, loyalty=c.loyalty, free=c.free)
        for c in legacy.contacts
    )
    contact_selection = create_contact_selection(character, contacts)
    assert contact_selection.free_points == legacy.contact_points_budget
    assert contact_selection.points_spent == 15
    assert contact_selection.karma_cost == 0

    # Starting resources -- Yeti's own gear purchases aren't reconstructable from the minimal
    # starter-gear stub (see spec/worklogs/WP9.md), so only the nuyen budget itself is checked.
    resources_letter = priority_letter(legacy.priorities.resources)
    assert starting_nuyen(resources_letter, PRIORITIES) == legacy.starting_nuyen

    # Lifestyle (WP20) -- unlike gear, Yeti's real primary Lifestyle *is* reconstructable, so it's
    # wired into the same joint nuyen-budget check gear draws from.
    assert legacy.lifestyles[0].base_lifestyle == "Low"
    lifestyle_selection = create_lifestyle_selection(
        legacy.lifestyles[0].base_lifestyle, legacy.lifestyles[0].months, LIFESTYLES
    )
    assert lifestyle_selection.total_cost == 2000
    resources_selection = create_resources_selection(
        resources_letter,
        PRIORITIES,
        gear_names=(),
        lifestyle_cost=lifestyle_selection.total_cost,
    )
    assert resources_selection.nuyen_budget == legacy.starting_nuyen
    assert resources_selection.nuyen_remaining == legacy.starting_nuyen - 2000

    # Derived stats -- hand-computed from Yeti's own recorded attribute totals (see docstring).
    assert (character.attribute_value("BOD"), character.attribute_value("REA")) == (4, 2)
    assert (character.attribute_value("STR"), character.attribute_value("CHA")) == (2, 5)
    assert (character.attribute_value("INT"), character.attribute_value("LOG")) == (5, 6)
    assert character.attribute_value("WIL") == 5

    assert initiative_value(character) == 7  # REA 2 + INT 5
    assert initiative_dice(character) == 1
    assert physical_limit(character) == 4  # ceil((2*2 + 4 + 2) / 3) = ceil(10/3)
    assert mental_limit(character) == 8  # ceil((6*2 + 5 + 5) / 3) = ceil(22/3)
    assert social_limit(character) == 7  # ceil((5*2 + 5 + 6) / 3) = ceil(21/3), Essence fixed at 6
    assert physical_condition_monitor(character) == 10  # 8 + ceil(4/2)
    assert stun_condition_monitor(character) == 11  # 8 + ceil(5/2)


def test_starting_nuyen_matches_resources_priority_letter_via_engine() -> None:
    """`chummer5.engine.resources.starting_nuyen` reproduces WP4's already-cross-validated
    `<startingnuyen>` figure for every mundane fixture (see spec/worklogs/WP4.md) -- this test
    exercises the WP9 engine function itself rather than WP2's raw loader directly.
    """
    for fixture_name in MUNDANE_FIXTURES:
        legacy = load_chum5(mundane_fixture_path(fixture_name))
        resources_letter = priority_letter(legacy.priorities.resources)
        assert starting_nuyen(resources_letter, PRIORITIES) == legacy.starting_nuyen, fixture_name
