"""Synthetic whole-character fixture harness (Phase S / WP72).

The legacy `.chum5` corpus is a fixed snapshot of 34 real characters, only one of which
(`Yeti-#ffffff2`) is a mundane Priority build (see the Implementation Plan's corpus note and
`spec/plan/phase-s-test-fixtures.md`). That structural thinness means every *interaction between
subsystems* — a Priority build that also bears cyberware, a magician who also loses Essence, a
Step-Seven leftover-Karma spend — has no real fixture; the WP59 research pass confirmed the corpus
can't grow (the legacy test harness only round-trips existing saves, it never emits a computed
character), and that hand-authoring fake `.chum5` files is strictly worse than an honest synthetic
fixture (see `spec/worklogs/WP59.md`).

This module is the honest alternative: a `SyntheticCharacter` input literal describing a full
chargen input, fed through the *real* engine (`create_character()` + the same selection functions
the web routes call), paired with a hand-derived `expected` table whose every entry carries an
inline citation to the rulebook / `priorities.xml` / legacy C#. It's the WP5/WP30
synthetic-primitive pattern (`test_improvements.py`, the Essence unit tests) extended from "one
mechanism in isolation" to "one whole character exercising an interaction" — exactly the axis the
`.chum5` corpus can't cover.
It sits *beside* the `.chum5` registry (`mundane_chum5.py`), not in place of it: the 11-file legacy
corpus stays the ground truth for build-method-agnostic derived-stat formulas; synthetic fixtures
cover interactions the corpus structurally lacks.

## Scope of this harness (WP72) and how later Phase-S WPs extend it

WP72 establishes the substrate and proves it end to end with **one** reference fixture: a full
mundane Priority build (`REFERENCE_MUNDANE_FIXTURE` in `synthetic_fixtures.py`). The
`SyntheticCharacter` dataclass therefore declares only the inputs a mundane build exercises —
priorities, metatype, attribute allocation, skill/group allocation + specializations, and a
positive/negative quality pair.

The later fixture-authoring WPs each **add their own input field(s) to `SyntheticCharacter` and the
matching wiring to `build_synthetic()` together**, mirroring how WP4 grew its `.chum5` parser one
field at a time rather than speculatively modelling shapes no fixture yet exercises (the same
"don't build past what's asked or verified" discipline the acceptance criteria call for):
- WP73 — cyberware + bioware Essence stacking (gaps G1/G2)
- WP74 — magician + cyberware Essence→Magic loss, foci/mentor (G3/G6)
- WP75 — Step-Seven leftover-Karma spend (G4/G5)
- WP76 — Sum-to-Ten whole-character (G7)

Fixture authoring is name-keyed for legibility: `skill_points`/`group_points`/`specializations` and
`qualities` are keyed by human-readable catalog name (Sneaking, Firearms, Catlike), not by the
opaque GUIDs the engine's own selection APIs take — `build_synthetic()` resolves names to ids
against the loaded catalogs, raising a clear error on an unknown name rather than letting it fall
through.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import Skill, load_skills
from chummer5.engine.character import (
    Character,
    create_character,
    metatype_choices,
)
from chummer5.engine.derived import (
    essence,
    initiative_dice,
    initiative_value,
    mental_limit,
    physical_condition_monitor,
    physical_limit,
    social_limit,
    stun_condition_monitor,
)
from chummer5.engine.qualities import (
    apply_quality_improvements,
    create_quality_selection,
)
from chummer5.engine.skills import create_skill_allocation, dice_pool, skill_rating

# Loaded once — the harness is a test dependency, so a module-level cache is fine (the same shape
# `tests/integration/test_character_fixtures.py` already uses for these loaders).
_METATYPES = load_metatypes()
_PRIORITIES = load_priorities()
_SKILLS = load_skills()
_QUALITIES = load_qualities()

_SKILLS_BY_NAME = {s.name: s for s in _SKILLS}
_QUALITIES_BY_NAME = {q.name: q for q in _QUALITIES}

# The five Priority categories a full build assigns a distinct letter to. Talent is forced to E
# (mundane) for every WP72-scope fixture — see the module docstring and the Project Overview's MVP
# scope — so it isn't a declarable field yet; the other four are.
_MVP_LETTERS = frozenset("ABCDE")


@dataclass(frozen=True)
class SyntheticCharacter:
    """A hand-authored whole-character chargen input, fed through the real engine by
    `build_synthetic()`. See this module's docstring for why this exists and how later Phase-S WPs
    extend it.

    Every collection field is keyed by human-readable catalog *name* (not the engine's GUID ids),
    resolved in `build_synthetic()`:
    - `attribute_points`: `{attribute code: points spent above the metatype minimum}`, including EDG
      (funded from the Heritage special-attribute-points pool, the same split `create_character`
      validates). Attribute codes are the engine's own (`BOD`/`AGI`/.../`EDG`), not localised names.
    - `skill_points`: `{skill name: points spent on that individual skill}`.
    - `group_points`: `{skill group name: points spent on that group}`.
    - `specializations`: `{skill name: specialization text}` (each costs 1 skill point, per WP50).
    - `qualities`: catalog names of the selected qualities (positive and negative alike).

    `expected` maps a metric key (see `resolve_metric`) to its hand-derived target value;
    `citations` maps each of those keys to the source the value was derived from (a `priorities.xml`
    figure, a `learnings/phase-*.md` formula, a legacy C# getter, ...). `build_synthetic_fixture`'s
    test asserts every `expected` key both computes to its target *and* carries a citation — a magic
    number with no cited source is itself a test failure, the honesty standard the worklogs'
    "hand-verified" caveats already hold themselves to, now executable.
    """

    name: str
    metatype: str
    heritage_letter: str
    attributes_letter: str
    skills_letter: str
    resources_letter: str
    attribute_points: Mapping[str, int]
    expected: Mapping[str, object]
    citations: Mapping[str, str]
    skill_points: Mapping[str, int] = field(default_factory=dict)
    group_points: Mapping[str, int] = field(default_factory=dict)
    specializations: Mapping[str, str] = field(default_factory=dict)
    qualities: tuple[str, ...] = ()


def _skill_by_name(name: str) -> Skill:
    skill = _SKILLS_BY_NAME.get(name)
    if skill is None:
        raise KeyError(f"synthetic fixture names an unknown skill: {name!r}")
    return skill


def build_synthetic(fixture: SyntheticCharacter) -> Character:
    """Run a `SyntheticCharacter` through the real engine, returning the finalized `Character`.

    Drives exactly the public engine API the web routes use — `create_character()`,
    `create_skill_allocation()`, `create_quality_selection()` + `apply_quality_improvements()` —
    so a fixture exercises the same code paths a real build does, not a test-only shortcut. The
    returned `Character` carries `skill_allocation`/`quality_selection` and its populated
    `ImprovementIndex`; `resolve_metric` reads every asserted value off it.
    """
    # A full build assigns Talent to E (mundane) and the other four categories a distinct letter.
    # Validate the four declared letters are individually legal and jointly distinct — a mundane
    # Priority build can't reuse a letter across categories (see the Priority Table, p.65).
    letters = (
        fixture.heritage_letter,
        fixture.attributes_letter,
        fixture.skills_letter,
        fixture.resources_letter,
    )
    for letter in letters:
        if letter not in _MVP_LETTERS:
            raise ValueError(f"not a Priority letter A-E: {letter!r}")
    if len(set(letters)) != len(letters):
        raise ValueError(f"Priority letters must be distinct across categories, got {letters}")

    heritage = _PRIORITIES.heritage[fixture.heritage_letter]
    choice = next(
        (c for c in metatype_choices(heritage, _METATYPES) if c.metatype.name == fixture.metatype),
        None,
    )
    if choice is None:
        raise ValueError(
            f"{fixture.metatype!r} is not an SR5-core metatype available at Heritage "
            f"{fixture.heritage_letter}"
        )

    character = create_character(
        metatype_choice=choice,
        heritage_letter=fixture.heritage_letter,
        attributes_letter=fixture.attributes_letter,
        priorities=_PRIORITIES,
        attribute_points=fixture.attribute_points,
    )

    skill_points = {_skill_by_name(n).id: p for n, p in fixture.skill_points.items()}
    specializations = {_skill_by_name(n).id: text for n, text in fixture.specializations.items()}
    allocation = create_skill_allocation(
        letter=fixture.skills_letter,
        priorities=_PRIORITIES,
        skills=_SKILLS,
        skill_points=skill_points,
        group_points=dict(fixture.group_points),
        specializations=specializations,
    )
    character = replace(character, skill_allocation=allocation)

    if fixture.qualities:
        quality_ids = []
        for quality_name in fixture.qualities:
            quality = _QUALITIES_BY_NAME.get(quality_name)
            if quality is None:
                raise KeyError(f"synthetic fixture names an unknown quality: {quality_name!r}")
            quality_ids.append(quality.id)
        selection = create_quality_selection(quality_ids, _QUALITIES)
        # apply_quality_improvements mutates the character's (already-linked) ImprovementIndex in
        # place — the same order test_character_fixtures.py uses (create_character, then apply).
        apply_quality_improvements(character, selection.qualities)
        character = replace(character, quality_selection=selection)

    return character


def resolve_metric(character: Character, key: str) -> object:
    """Compute one named derived metric off a finalized synthetic `Character`.

    Key grammar (so a fixture's `expected`/`citations` keys read as documentation of what's
    asserted):
    - `attr:<CODE>`         — `Character.attribute_value(CODE)` (e.g. `attr:BOD`, `attr:EDG`)
    - `rating:<SkillName>`  — `skill_rating(...)` (final rating incl. group/improvement bonuses)
    - `pool:<SkillName>`    — `dice_pool(...)` (rating + linked attribute, +2 if specialized)
    - `initiative` / `initiative_dice`
    - `limit:physical` / `limit:mental` / `limit:social`
    - `cm:physical` / `cm:stun`
    - `essence`             — the exact `Decimal` Essence (unrounded)
    - `karma_spent` / `karma_remaining`

    A key naming a skill requires the fixture to have committed a `skill_allocation` (every WP72
    fixture does). Raises `KeyError` on an unrecognised key rather than silently returning `None`.
    """
    if key.startswith("attr:"):
        return character.attribute_value(key[len("attr:") :])
    if key.startswith("rating:"):
        assert character.skill_allocation is not None
        skill = _skill_by_name(key[len("rating:") :])
        return skill_rating(character, character.skill_allocation, skill)
    if key.startswith("pool:"):
        assert character.skill_allocation is not None
        skill = _skill_by_name(key[len("pool:") :])
        return dice_pool(character, character.skill_allocation, skill)

    fixed = {
        "initiative": initiative_value,
        "initiative_dice": initiative_dice,
        "limit:physical": physical_limit,
        "limit:mental": mental_limit,
        "limit:social": social_limit,
        "cm:physical": physical_condition_monitor,
        "cm:stun": stun_condition_monitor,
        "essence": essence,
        "karma_spent": lambda c: c.karma_spent,
        "karma_remaining": lambda c: c.karma_remaining,
    }
    if key in fixed:
        return fixed[key](character)
    raise KeyError(f"resolve_metric: unrecognised metric key {key!r}")


def _decimal(value: object) -> object:
    """Normalise an expected value for comparison — an `essence` target authored as `6` or `6.0`
    compares equal to the engine's `Decimal("6")`.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    return value


def assert_fixture(fixture: SyntheticCharacter) -> None:
    """Build `fixture` through the real engine and assert every `expected` metric matches, and that
    each asserted key carries a citation. Shared by every synthetic-fixture test so the "cited or
    it's a failure" contract is enforced uniformly, not re-implemented per fixture.
    """
    character = build_synthetic(fixture)
    for key, target in fixture.expected.items():
        actual = resolve_metric(character, key)
        if key == "essence":
            assert _decimal(actual) == _decimal(target), (fixture.name, key, actual, target)
        else:
            assert actual == target, (fixture.name, key, actual, target)
        assert key in fixture.citations and fixture.citations[key].strip(), (
            f"{fixture.name}: expected metric {key!r} has no citation"
        )
