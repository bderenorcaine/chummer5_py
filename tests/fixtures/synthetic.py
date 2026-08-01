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
- WP73 — cyberware + bioware Essence stacking (gaps G1/G2) — **landed**: adds the `cyberware`/
  `bioware` name-list fields below, wired through `create_cyberware_tree_selection`/
  `create_bioware_selection` in the fixed cyberware-first, bioware-second evaluation order those
  engine modules document (bioware sees cyberware's already-resolved Essence via
  `other_essence_spent`), plus the `cyberware:*`/`bioware:*` metric keys `resolve_metric` reads off
  the resulting selections.
- WP74 — magician + cyberware Essence→Magic loss, foci/mentor (G3/G6) — **landed**: adds the
  `magic_type`/`talent_letter`/`tradition`/`magic_granted_skills`/`spells`/`mentor_spirit`/`foci`
  fields below, wired through `create_magic_selection` (a full Priority build now assigns Talent a
  real A-D letter instead of the mundane-only forced E), `create_quality_selection`'s Mentor Spirit
  path, `create_spell_selection`, and `create_foci_selection`. Cyberware is applied *before* spells
  and foci so both see the Essence-reduced Magic rating (`attribute_value("MAG")`) their caps read,
  the exact Essence→Magic interaction G3 exists to test. Adds the `magic:*`/`drain_resistance`/
  `power_points`/`foci:*`/`spells:*` metric keys.
- WP75 — Step-Seven leftover-Karma spend (G4/G5) — **landed**: adds the `karma_attribute_points`/
  `karma_skill_points`/`karma_group_points`/`karma_specializations` fields below, wired through
  `create_karma_attribute_points` and `create_karma_skill_selection` in that order, *before* the
  spell block — the same Step Seven evaluation order `chummer5.io.save_format.build_character`
  documents (each spend's `karma_budget` is `character.karma_remaining`, so it already reflects
  every earlier-committed spend, and a Karma-funded spell is checked against what the attribute/
  skill spends left). Adds the `karma_attribute:karma_cost`/`karma_skill:karma_cost`/
  `karma_skill:broken_groups` metric keys; the Karma-funded-spell side needed no new field at all
  (a fixture simply declares more `spells` than its Talent option's free budget).
- WP86 — cyberware purchase *trees* (the harness half of G8) — **landed**: retypes the `cyberware`
  field from a flat name list to `tuple[str | CyberwarePick, ...]`, so a fixture can declare a
  rating and nested plugins instead of only the rating-1, plugin-free leaves WP73-76 could express.
  A bare `"Datajack"` stays legal and means exactly what it always did (`CyberwarePick(name,
  rating=1, plugins=())`), so WP73-76's own literals are untouched. Adds the per-purchase Capacity
  metric keys (`cyberware:<path>:capacity_budget`/`:capacity_spent`/`:capacity_remaining`/
  `:capacity_cost`), which is what makes "this parent's plugins fill it exactly" assertable rather
  than merely "the engine didn't reject them" — the boundary case a real player build turned out to
  sit on.
- WP76 — Sum-to-Ten whole-character (G7) — **landed**: adds the `build_method` field below, which
  selects *which validity rule* `build_synthetic()` applies to the same five priority letters —
  Priority's bijection (distinct A-E, the only rule WP72-75 knew) or Sum-to-Ten's repeats-allowed,
  point-values-total-exactly-10 rule (`chummer5.engine.build_method.validate_sum_to_ten_total`).
  That's the whole engine-visible difference between the two build methods: `Character` has no
  `build_method` field at all (it's session/save-format state — see `chummer5.web.session`), and
  every budget downstream of the letters is read from the same `priorities.xml` rows either way.
  So no new metric key was needed: a Sum-to-Ten fixture's letter assignment is asserted *by
  construction* — `build_synthetic()` raises unless the five letters total exactly 10 — and the
  dedicated test in `tests/integration/test_synthetic_fixtures.py` additionally pins down that the
  same letters are rejected under `PRIORITY_BUILD_METHOD`.

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

from chummer5.data.bioware import Bioware, load_bioware
from chummer5.data.cyberware_subsystems import CyberwareEntry, load_cyberware_entries
from chummer5.data.foci import Focus, load_foci
from chummer5.data.mentors import load_mentors
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import Skill, load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.bioware import apply_bioware_improvements, create_bioware_selection
from chummer5.engine.build_method import (
    PRIORITY_BUILD_METHOD,
    SUM_TO_TEN_BUILD_METHOD,
    validate_sum_to_ten_total,
)
from chummer5.engine.character import (
    Character,
    create_character,
    create_karma_attribute_points,
    metatype_choices,
)
from chummer5.engine.cyberware_subsystems import (
    CyberwarePurchaseRequest,
    PurchasedCyberware,
    apply_cyberware_tree_improvements,
    create_cyberware_tree_selection,
    cyberlimb_attribute_maximums,
)
from chummer5.engine.derived import (
    drain_resistance,
    essence,
    initiative_dice,
    initiative_value,
    mental_limit,
    physical_condition_monitor,
    physical_limit,
    social_limit,
    stun_condition_monitor,
)
from chummer5.engine.foci import apply_foci_improvements, create_foci_selection
from chummer5.engine.magic import (
    apply_magic_skill_grant_improvements,
    create_magic_selection,
    create_spell_selection,
    offered_talent_options,
)
from chummer5.engine.qualities import (
    apply_mentor_spirit_improvements,
    apply_quality_improvements,
    create_quality_selection,
)
from chummer5.engine.skills import (
    create_karma_skill_selection,
    create_skill_allocation,
    dice_pool,
    skill_rating,
)

# Loaded once — the harness is a test dependency, so a module-level cache is fine (the same shape
# `tests/integration/test_character_fixtures.py` already uses for these loaders).
_METATYPES = load_metatypes()
_PRIORITIES = load_priorities()
_SKILLS = load_skills()
_QUALITIES = load_qualities()
_CYBERWARE = load_cyberware_entries()
_BIOWARE = load_bioware()
_TRADITIONS = load_traditions()
_SPELLS = load_spells()
_MENTORS = load_mentors()
_FOCI = load_foci()

_SKILLS_BY_NAME = {s.name: s for s in _SKILLS}
_QUALITIES_BY_NAME = {q.name: q for q in _QUALITIES}
_CYBERWARE_BY_NAME = {c.name: c for c in _CYBERWARE}
_BIOWARE_BY_NAME = {b.name: b for b in _BIOWARE}
_SPELLS_BY_NAME = {s.name: s for s in _SPELLS}
_FOCI_BY_NAME = {f.name: f for f in _FOCI}
_MENTORS_BY_NAME = {m.name: m for m in _MENTORS}
_TRADITIONS_BY_NAME = {t.name: t for t in _TRADITIONS}

# The five priority categories a full build assigns a letter to. Under the Priority build method
# those letters are a bijection onto A-E: a mundane fixture leaves `talent_letter` unset, so Talent
# defaults to E (mundane) and the other four take A-D (WP72/73); a magic fixture (WP74) declares
# `talent_letter` explicitly (a real A-D magic letter), so all five become a genuine permutation of
# A-E. Under Sum-to-Ten (WP76) letters may repeat instead, constrained only by their point values
# totalling exactly 10 -- see `_validate_letters` below.
_MVP_LETTERS = frozenset("ABCDE")


@dataclass(frozen=True)
class CyberwarePick:
    """One node of a fixture's cyberware purchase tree (WP86) — a name, a rating, and its plugins.

    The name-keyed authoring mirror of `chummer5.engine.cyberware_subsystems
    .CyberwarePurchaseRequest`, which is what `build_synthetic()` resolves this into. A plugin may
    itself be a bare name string, so a rated parent carrying rating-1 plugins reads as
    `CyberwarePick("Cyberears", 3, ("Balance Augmenter", "Spatial Recognizer"))` rather than three
    nested constructor calls.

    **A bundled subsystem is never declared here.** Rows like Cyberears/Cybereyes Basic System carry
    a free bundled item (Sound Link / Image Link) that `create_cyberware_tree_selection` installs
    itself; naming one explicitly is rejected by `cyberware_purchase_request()` rather than silently
    installing a second, paid-for copy alongside the free one.
    """

    name: str
    rating: int = 1
    plugins: tuple[CyberwarePick | str, ...] = ()


# What a fixture may write in `SyntheticCharacter.cyberware` and in a `CyberwarePick.plugins`: a
# bare catalog name (rating 1, no plugins -- every WP73-76 entry) or a full `CyberwarePick`.
CyberwareEntryPick = CyberwarePick | str


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
    - `quality_text`: `{quality name: free-text detail}` for the selected qualities that *require*
      one (a `BonusSupport.SELECT_TEXT` quality — e.g. SINner's SIN description, WP55). Must be
      present for exactly those and absent for every other quality, mirroring
      `create_quality_selection`'s own both-directions check.
    - `cyberware` / `bioware` (WP73, cyberware widened in WP86): the purchased cyberware/bioware.
      Both may name the same item more than once (a matched pair of cyberlimbs, say — duplicate
      purchases are legal, see `chummer5.engine.cyberware_subsystems`). A bioware entry is always a
      bare catalog name; a cyberware entry is a bare name (rating 1, no plugins — the only shape
      WP73-76 could express) *or* a `CyberwarePick` carrying a rating and nested plugins, which is
      what WP38/WP41/WP42 actually built and what a real player save contains. `build_synthetic()`
      resolves cyberware first (its Essence cost unaware of bioware) then bioware second (aware of
      cyberware's Essence via `other_essence_spent`), the fixed shared-pool evaluation order both
      engine modules document, and both draw from the fixture's Resources-priority nuyen (bioware
      from what cyberware left).
    - `magic_type` / `talent_letter` / `tradition` / `magic_granted_skills` (WP74): a magic build's
      Talent selection. `magic_type` is `"Magician"`/`"Adept"` (`None` = mundane, the default);
      `talent_letter` the Talent priority letter (a magic build's fifth priority slot — required
      whenever `magic_type` is set, and it must not collide with the other four); `tradition` a
      tradition *name* (`"Hermetic"`/`"Shamanic"`, Magician only); `magic_granted_skills` the
      catalog names picked for the Talent free-skill grant (exactly the option's `skill_qty`, each
      granted at the option's `skill_val` rating via an `ImprovementType.SKILL` improvement).
    - `spells` (WP74): catalog names of a Magician's chosen spells. Resolved *after* cyberware, so
      the "Magic Rating x 2" known-spells cap reads the Essence-reduced Magic rating.
    - `mentor_spirit` (WP74): a Mentor Spirit archetype *name* (e.g. `"Mountain"`). Selecting one
      requires `"Mentor Spirit"` among `qualities` and a magic-active `magic_type`; its General and
      Magician/Adept `FLAT_BONUS` slots land as `ImprovementSource.MENTOR_SPIRIT` improvements. Only
      single-General-option archetypes are supported (the General slot auto-resolves) — a two-option
      archetype would need a choice field added here, the same "extend when a fixture needs it"
      discipline WP73's cyberware/bioware fields followed.
    - `karma_attribute_points` / `karma_skill_points` / `karma_group_points` /
      `karma_specializations` (WP75): Step Seven's leftover-Karma spend, each mirroring its
      priority-budget-funded sibling field's own shape (`attribute_points`, `skill_points`,
      `group_points`, `specializations`) and meaning *additional* points bought with Karma on top of
      whatever the priority budget already funded. `karma_attribute_points` is keyed by attribute
      code (EDG included; MAG/RES are never Karma-allocatable — see `KarmaAttributeSelection`);
      the three skill-side maps are name-keyed like their siblings. Raising or specializing a member
      of an already-group-purchased skill group *breaks* that group (see
      `create_karma_skill_selection`) — assert the resulting split via `karma_skill:broken_groups`
      plus the members' own `rating:*` keys.
    - `build_method` (WP76): which letter-assignment rule the five priority letters are validated
      against — `PRIORITY_BUILD_METHOD` (the default; five distinct letters) or
      `SUM_TO_TEN_BUILD_METHOD` (repeats allowed, the five letters' point values must total exactly
      `SUM_TO_TEN_TARGET`). Nothing downstream of that check differs: both methods read the same
      `priorities.xml` budgets off the same letters, and `Character` carries no build-method field
      of its own.
    - `foci` (WP74): `(focus name, Force)` pairs to bond. Resolved *after* cyberware too, so the
      count cap (<= Magic) and total-Force cap (<= Magic x 2) read the Essence-reduced Magic rating;
      nuyen is drawn from whatever the Resources pool has left after cyberware/bioware, Karma from
      `character.karma_remaining`.

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
    build_method: str = PRIORITY_BUILD_METHOD
    skill_points: Mapping[str, int] = field(default_factory=dict)
    group_points: Mapping[str, int] = field(default_factory=dict)
    specializations: Mapping[str, str] = field(default_factory=dict)
    qualities: tuple[str, ...] = ()
    quality_text: Mapping[str, str] = field(default_factory=dict)
    cyberware: tuple[CyberwareEntryPick, ...] = ()
    bioware: tuple[str, ...] = ()
    magic_type: str | None = None
    talent_letter: str | None = None
    tradition: str | None = None
    magic_granted_skills: tuple[str, ...] = ()
    spells: tuple[str, ...] = ()
    mentor_spirit: str | None = None
    foci: tuple[tuple[str, int], ...] = ()
    karma_attribute_points: Mapping[str, int] = field(default_factory=dict)
    karma_skill_points: Mapping[str, int] = field(default_factory=dict)
    karma_group_points: Mapping[str, int] = field(default_factory=dict)
    karma_specializations: Mapping[str, str] = field(default_factory=dict)


def _skill_by_name(name: str) -> Skill:
    skill = _SKILLS_BY_NAME.get(name)
    if skill is None:
        raise KeyError(f"synthetic fixture names an unknown skill: {name!r}")
    return skill


def _cyberware_by_name(name: str) -> CyberwareEntry:
    item = _CYBERWARE_BY_NAME.get(name)
    if item is None:
        raise KeyError(f"synthetic fixture names an unknown cyberware item: {name!r}")
    return item


def cyberware_purchase_request(pick: CyberwareEntryPick) -> CyberwarePurchaseRequest:
    """Resolve one authoring-side `CyberwarePick` (or bare name) into the engine's own request type.

    Names resolve to ids here, the same "fixtures are name-keyed, the engine is id-keyed" split
    every other field follows, so an unknown name raises a clear `KeyError` instead of reaching
    `create_cyberware_tree_selection` as an id it can't find.

    A pick naming its parent's *bundled* subsystem is rejected: those are resolved by the engine
    (`CyberwareEntry.bundled_subsystem_names` -> a `bundled_free` install), so declaring one would
    quietly buy a second copy at full price and silently inflate both the nuyen and the Capacity
    figures a fixture exists to pin down. WP86's own acceptance criteria call this out as an error
    rather than a duplicate.
    """
    if isinstance(pick, str):
        pick = CyberwarePick(name=pick)
    item = _cyberware_by_name(pick.name)
    bundled = {name.casefold() for name in item.bundled_subsystem_names}
    plugins = []
    for plugin in pick.plugins:
        plugin_name = plugin if isinstance(plugin, str) else plugin.name
        if plugin_name.casefold() in bundled:
            raise ValueError(
                f"synthetic fixture declares {plugin_name!r} as a plugin of {pick.name!r}, but "
                f"that item is bundled free with its parent and is installed by the engine"
            )
        plugins.append(cyberware_purchase_request(plugin))
    return CyberwarePurchaseRequest(item_id=item.id, rating=pick.rating, plugins=tuple(plugins))


def _bioware_by_name(name: str) -> Bioware:
    item = _BIOWARE_BY_NAME.get(name)
    if item is None:
        raise KeyError(f"synthetic fixture names an unknown bioware item: {name!r}")
    return item


def _focus_by_name(name: str) -> Focus:
    item = _FOCI_BY_NAME.get(name)
    if item is None:
        raise KeyError(f"synthetic fixture names an unknown focus: {name!r}")
    return item


def _validate_letters(build_method: str, letters: tuple[str, ...]) -> None:
    """Validate a fixture's five priority letters under its build method (WP76).

    Mirrors `chummer5.web.routes.priorities.submit_priorities`, which is the *only* place the real
    app enforces letter-assignment shape either (`create_character` never validated it — it just
    reads budgets off whatever letters it's handed), so a fixture is held to the same rule a player
    submission is:
    - `PRIORITY_BUILD_METHOD`: five distinct letters, one each of A-E (the Priority Table, p.65).
    - `SUM_TO_TEN_BUILD_METHOD`: repeats allowed; the five letters' point values must total exactly
      `SUM_TO_TEN_TARGET` (10) — exact equality, not a ceiling, per
      `chummer5.engine.build_method`'s own docstring. Note this is legacy-Chummer/errata content,
      not a core-rulebook mechanic (WP44 confirmed zero PDF hits for "sum to ten").

    An unrecognised build method raises rather than falling back to either real rule, the same way
    the route itself itemises it as an error instead of guessing.
    """
    for letter in letters:
        if letter not in _MVP_LETTERS:
            raise ValueError(f"not a priority letter A-E: {letter!r}")
    if build_method == PRIORITY_BUILD_METHOD:
        if len(set(letters)) != len(letters):
            raise ValueError(f"Priority letters must be distinct across categories, got {letters}")
    elif build_method == SUM_TO_TEN_BUILD_METHOD:
        validate_sum_to_ten_total(letters)
    else:
        raise ValueError(f"unsupported build method: {build_method!r}")


def build_synthetic(fixture: SyntheticCharacter) -> Character:
    """Run a `SyntheticCharacter` through the real engine, returning the finalized `Character`.

    Drives exactly the public engine API the web routes use — `create_character()`,
    `create_skill_allocation()`, `create_quality_selection()` + `apply_quality_improvements()` —
    so a fixture exercises the same code paths a real build does, not a test-only shortcut. The
    returned `Character` carries `skill_allocation`/`quality_selection` and its populated
    `ImprovementIndex`; `resolve_metric` reads every asserted value off it.

    The five priority letters are validated first, under the fixture's own `build_method`
    (`_validate_letters`) — the one check no engine function downstream performs.
    """
    if fixture.magic_type is not None and fixture.talent_letter is None:
        raise ValueError("a magic build must declare talent_letter (its fifth Priority slot)")
    talent_letter = fixture.talent_letter or "E"
    _validate_letters(
        fixture.build_method,
        (
            fixture.heritage_letter,
            fixture.attributes_letter,
            fixture.skills_letter,
            fixture.resources_letter,
            talent_letter,
        ),
    )

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

    # Magic (WP74): resolve the Talent selection before qualities (a Mentor Spirit pick needs
    # `magic_type`) and before cyberware/spells/foci (those read the eventual Magic rating). The
    # free-skill grant's rating lands as an ImprovementType.SKILL improvement, exactly as the web
    # layer does it.
    if fixture.magic_type is not None:
        tradition_id = (
            _TRADITIONS_BY_NAME[fixture.tradition].id if fixture.tradition is not None else None
        )
        granted_ids = [_skill_by_name(n).id for n in fixture.magic_granted_skills]
        magic_selection = create_magic_selection(
            talent_letter,
            fixture.magic_type,
            tradition_id,
            granted_ids,
            _PRIORITIES,
            _TRADITIONS,
            _SKILLS,
        )
        character = replace(
            character,
            magic_type=magic_selection.magic_type,
            magic_rating=magic_selection.magic_rating,
            tradition=magic_selection.tradition,
            magic_granted_skill_ids=magic_selection.granted_skill_ids,
        )
        apply_magic_skill_grant_improvements(character, magic_selection, _SKILLS)

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
        # quality_text is authored name-keyed for legibility; the engine keys it by quality id.
        quality_text = {}
        for quality_name, text in fixture.quality_text.items():
            quality = _QUALITIES_BY_NAME.get(quality_name)
            if quality is None:
                raise KeyError(f"synthetic fixture names an unknown quality: {quality_name!r}")
            quality_text[quality.id] = text
        # WP74: a Mentor Spirit archetype pick (name-keyed, resolved to its id) rides on the quality
        # selection. Its General slot auto-resolves (single-option archetypes only — see
        # SyntheticCharacter's docstring); the Magician/Adept slot is auto-resolved from magic_type.
        mentor_archetype_id = (
            _MENTORS_BY_NAME[fixture.mentor_spirit].id
            if fixture.mentor_spirit is not None
            else None
        )
        selection = create_quality_selection(
            quality_ids,
            _QUALITIES,
            magic_type=character.magic_type,
            mentor_catalog=_MENTORS,
            mentor_spirit_archetype_id=mentor_archetype_id,
            quality_text=quality_text,
        )
        # apply_quality_improvements mutates the character's (already-linked) ImprovementIndex in
        # place — the same order test_character_fixtures.py uses (create_character, then apply).
        apply_quality_improvements(character, selection.qualities)
        if selection.mentor_spirit is not None:
            apply_mentor_spirit_improvements(character, selection.mentor_spirit)
        character = replace(character, quality_selection=selection)

    if fixture.cyberware or fixture.bioware:
        # Cyberware and bioware draw from one shared Resources-priority nuyen pool and reduce one
        # shared Essence pool. The engine resolves them in a fixed order — cyberware first (unaware
        # of bioware), bioware second (aware of cyberware) — see chummer5.engine.bioware's docstring
        # for why. The fixture models no gear/Lifestyle spend, so the full Resources nuyen is
        # available to the two of them; bioware sees what cyberware left, mirroring the web layer.
        nuyen_budget = _PRIORITIES.resources[fixture.resources_letter].nuyen

        cyberware_selection = create_cyberware_tree_selection(
            [cyberware_purchase_request(pick) for pick in fixture.cyberware],
            _CYBERWARE,
            nuyen_budget,
            attribute_maximums=cyberlimb_attribute_maximums(character),
        )
        apply_cyberware_tree_improvements(character, cyberware_selection)
        character = replace(character, cyberware_selection=cyberware_selection)

        bioware_selection = create_bioware_selection(
            [_bioware_by_name(n).id for n in fixture.bioware],
            _BIOWARE,
            nuyen_budget - cyberware_selection.nuyen_spent,
            other_essence_spent=cyberware_selection.essence_spent,
        )
        apply_bioware_improvements(character, bioware_selection)
        character = replace(character, bioware_selection=bioware_selection)

    # Step Seven's leftover-Karma spend (WP75), in the fixed order
    # `chummer5.io.save_format.build_character` documents: attributes first, then skills, each
    # validated against `character.karma_remaining` *at that point* — so every spend sees the
    # already-committed ones' cost, and no two can silently double-spend the same Karma. Both come
    # before the spell block below for the same reason (a Karma-funded spell is checked against
    # what these left).
    if fixture.karma_attribute_points:
        character = replace(
            character,
            karma_attribute_selection=create_karma_attribute_points(
                character,
                dict(fixture.karma_attribute_points),
                karma_budget=character.karma_remaining,
            ),
        )

    if fixture.karma_skill_points or fixture.karma_group_points or fixture.karma_specializations:
        character = replace(
            character,
            karma_skill_selection=create_karma_skill_selection(
                character,
                _SKILLS,
                karma_skill_points={
                    _skill_by_name(n).id: p for n, p in fixture.karma_skill_points.items()
                },
                karma_group_points=dict(fixture.karma_group_points),
                karma_specializations={
                    _skill_by_name(n).id: text for n, text in fixture.karma_specializations.items()
                },
                karma_budget=character.karma_remaining,
            ),
        )

    # Spells and Foci (WP74) come *after* cyberware/bioware so both read the Essence-reduced Magic
    # rating (`attribute_value("MAG")`): the "Magic Rating x 2" spell cap and the foci count/Force
    # caps all key off the finished MAG, so the Essence→Magic loss (G3) actually constrains them.
    if fixture.spells:
        # The free spell budget is the chosen Magician Talent option's own `spells` field (Adept has
        # none). Resolve it from the offered options for this fixture's Talent letter.
        magician_option = next(
            (
                o
                for o in offered_talent_options(talent_letter, _PRIORITIES)
                if o.codename == fixture.magic_type
            ),
            None,
        )
        spell_budget = (magician_option.spells or 0) if magician_option is not None else 0
        spell_selection = create_spell_selection(
            [_SPELLS_BY_NAME[n].id for n in fixture.spells],
            _SPELLS,
            budget=spell_budget,
            magic_rating=character.attribute_value("MAG"),
            karma_budget=character.karma_remaining,
        )
        character = replace(character, spell_selection=spell_selection)

    if fixture.foci:
        # Foci draw nuyen from whatever the Resources pool has left after cyberware/bioware, and
        # Karma from the unified ledger (Phase O) — the same shared-pool accounting the web layer
        # does. No bound spirits in any current fixture, so nothing precedes foci in the Karma
        # order.
        spent_nuyen = 0
        if character.cyberware_selection is not None:
            spent_nuyen += character.cyberware_selection.nuyen_spent
        if character.bioware_selection is not None:
            spent_nuyen += character.bioware_selection.nuyen_spent
        foci_selection = create_foci_selection(
            [(_focus_by_name(n).id, force) for n, force in fixture.foci],
            character,
            _FOCI,
            nuyen_budget=_PRIORITIES.resources[fixture.resources_letter].nuyen - spent_nuyen,
            karma_budget=character.karma_remaining,
        )
        apply_foci_improvements(character, foci_selection)
        character = replace(character, foci_selection=foci_selection)

    return character


_CAPACITY_FIELDS = {
    "capacity_budget": lambda p: p.capacity_budget,
    "capacity_spent": lambda p: p.capacity_spent,
    "capacity_remaining": lambda p: p.capacity_remaining,
    "capacity_cost": lambda p: p.capacity_cost,
}


def _capacity_metric(
    purchases: tuple[PurchasedCyberware, ...], path: str, field_name: str
) -> Decimal:
    """Read one Capacity figure off the purchase tree, addressed by a `/`-separated name path.

    `Cyberears` names a top-level purchase; `Cyberears/Audio Enhancement` names the plugin installed
    into it. An ambiguous path (two purchases of the same name — legal, e.g. a matched pair of
    cyberlimbs) raises rather than silently answering for the first: a fixture that means one of two
    identical limbs needs a way to say *which*, and inventing an index here before any fixture needs
    one would be building past the ask. The same "extend when a fixture needs it" discipline every
    field on `SyntheticCharacter` already follows.
    """
    read = _CAPACITY_FIELDS.get(field_name)
    if read is None:
        raise KeyError(f"resolve_metric: unrecognised cyberware Capacity field {field_name!r}")
    node: PurchasedCyberware | None = None
    level = purchases
    for segment in path.split("/"):
        matches = [p for p in level if p.item.name == segment]
        if not matches:
            raise KeyError(f"resolve_metric: no purchased cyberware named {segment!r} in {path!r}")
        if len(matches) > 1:
            raise KeyError(
                f"resolve_metric: {segment!r} is ambiguous in {path!r} "
                f"({len(matches)} purchases share that name)"
            )
        node = matches[0]
        level = node.plugins
    assert node is not None  # a path always has at least one segment
    return read(node)


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
    - `essence`             — the exact `Decimal` Essence (unrounded) of the whole character
    - `cyberware:essence_spent` / `cyberware:nuyen_spent` (WP73) — this selection's own totals
    - `cyberware:<name path>:capacity_budget` / `:capacity_spent` / `:capacity_remaining` /
      `:capacity_cost` (WP86) — one node of the purchase tree's Capacity figures, addressed by a
      `/`-separated path of catalog names (`Cyberears`, `Cyberears/Audio Enhancement`).
      `capacity_budget`/`capacity_spent`/`capacity_remaining` are what a *parent* offers, has taken,
      and has left; `capacity_cost` is what a *plugin* charges its parent. Asserting a parent's
      `capacity_remaining` as 0 is the only way to state "the plugins fill it exactly" — the engine
      itself only ever checks that they fit
    - `bioware:essence_spent` / `bioware:nuyen_spent` (WP73) — likewise, so the shared-pool split is
      asserted per-source, not only via the combined `essence`
    - `magic:rating` (WP74) — the finished, Essence-reduced Magic rating (`attribute_value("MAG")`)
    - `magic:rating_before_essence_loss` / `magic:essence_loss` (WP74) — the pre-loss rating and the
      ceiling'd Essence-driven reduction, so the G3 interaction is asserted on both sides
    - `drain_resistance` (WP74) — the Drain Resistance dice pool (Magician: tradition pair; else
      None)
    - `power_points` (WP74) — Adept Power Points (0 for a Magician, asserting the type distinction)
    - `foci:nuyen_cost` / `foci:karma_cost` (WP74) — the bonded-foci spend
    - `spells:count` / `spells:karma_cost` (WP74) — spells known and their leftover-Karma cost
    - `karma_attribute:karma_cost` (WP75) — the Step Seven attribute spend's own Karma cost (the
      resulting *value* is already visible through `attr:<CODE>`, which sums both point sources)
    - `karma_skill:karma_cost` / `karma_skill:broken_groups` (WP75) — the Step Seven skill-side
      spend's own Karma cost, and the set of skill-group names it broke (a `frozenset[str]`)
    - `karma_spent` / `karma_remaining`

    A key naming a skill requires the fixture to have committed a `skill_allocation` (every WP72
    fixture does); a `cyberware:`/`bioware:`/`karma_attribute:`/`karma_skill:` key requires the
    matching selection to exist. Raises `KeyError` on an unrecognised key rather than silently
    returning `None`.
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
    if key.startswith("cyberware:") and key.count(":") == 2:
        _, path, field_name = key.split(":")
        assert character.cyberware_selection is not None
        return _capacity_metric(character.cyberware_selection.purchases, path, field_name)
    if key == "cyberware:essence_spent":
        assert character.cyberware_selection is not None
        return character.cyberware_selection.essence_spent
    if key == "cyberware:nuyen_spent":
        assert character.cyberware_selection is not None
        return character.cyberware_selection.nuyen_spent
    if key == "bioware:essence_spent":
        assert character.bioware_selection is not None
        return character.bioware_selection.essence_spent
    if key == "bioware:nuyen_spent":
        assert character.bioware_selection is not None
        return character.bioware_selection.nuyen_spent
    if key == "foci:nuyen_cost":
        assert character.foci_selection is not None
        return character.foci_selection.nuyen_cost
    if key == "foci:karma_cost":
        assert character.foci_selection is not None
        return character.foci_selection.karma_cost
    if key == "spells:count":
        assert character.spell_selection is not None
        return len(character.spell_selection.spells)
    if key == "spells:karma_cost":
        assert character.spell_selection is not None
        return character.spell_selection.karma_cost
    if key == "karma_attribute:karma_cost":
        assert character.karma_attribute_selection is not None
        return character.karma_attribute_selection.karma_cost
    if key == "karma_skill:karma_cost":
        assert character.karma_skill_selection is not None
        return character.karma_skill_selection.karma_cost
    if key == "karma_skill:broken_groups":
        assert character.karma_skill_selection is not None
        return character.karma_skill_selection.broken_groups

    fixed = {
        "initiative": initiative_value,
        "initiative_dice": initiative_dice,
        "limit:physical": physical_limit,
        "limit:mental": mental_limit,
        "limit:social": social_limit,
        "cm:physical": physical_condition_monitor,
        "cm:stun": stun_condition_monitor,
        "essence": essence,
        "drain_resistance": drain_resistance,
        "magic:rating": lambda c: c.attribute_value("MAG"),
        "magic:rating_before_essence_loss": lambda c: c.magic_rating_before_essence_loss,
        "magic:essence_loss": lambda c: c.magic_essence_loss,
        "power_points": lambda c: c.power_points,
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
        # Essence figures are `Decimal`; normalise both sides so a fixture may author `2.4`/`3.1`
        # as an int/float/Decimal literal and still compare equal to the engine's `Decimal`. Covers
        # the whole-character `essence` and the per-source `*:essence_spent` metrics alike.
        if isinstance(actual, Decimal) or isinstance(target, Decimal):
            assert _decimal(actual) == _decimal(target), (fixture.name, key, actual, target)
        else:
            assert actual == target, (fixture.name, key, actual, target)
        assert key in fixture.citations and fixture.citations[key].strip(), (
            f"{fixture.name}: expected metric {key!r} has no citation"
        )
