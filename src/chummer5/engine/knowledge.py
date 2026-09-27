"""Knowledge & Language skill selection (WP49).

Composes `chummer5.data.knowledge`'s category/attribute reference data with WP6's `Character` into
a buildable free-point Knowledge/Language spend. Mundane-and-magic-agnostic -- nothing here reads
`magic_type`, so it applies identically to every character this engine can build.

**A player-authored pick, not a catalog selection** -- mirrors `chummer5.engine.resources.Contact`
exactly (see that class's own docstring): a Knowledge/Language skill's name is the player's own
invention, not rules data, so `KnowledgeSkillPick`/`LanguageSkillPick` carry a freeform `name`
rather than cross-referencing an id against a fixed catalog. `chummer5.data.knowledge`'s categories/
suggested-name lists are hints for the picker UI only, never validated against.

**Free-point budget: `(Intuition + Logic) * 2`** (core rulebook p. 89, "KNOWLEDGE AND LANGUAGE
SKILLS" -- see `spec/rulebooks/learnings.md`'s WP49 entry for the full citation). Spent the same way
as other skill points (1 point = 1 rank), capped per-entry at `chummer5.engine.skills
.MAX_SKILL_RATING_CREATE` (6) -- the rulebook's own "no character may possess a knowledge or a
language skill higher than rating 6" is the identical number, not a coincidence (both are Step
Five's shared chargen-time skill-rating ceiling). **Not enforced as a required full spend** --
mirrors `chummer5.engine.skills.create_skill_allocation`'s own established "doesn't require the full
budget to be spent" precedent (see that module's docstring) rather than the rulebook's adjacent "all
skill and skill-group points must be spent" line, which this project already didn't enforce for the
sibling Active-skill budget either.

**WP125: Active-skill points fund Knowledge/Language spend past the free pool.** p. 88: "These
skill points are generally used to purchase Active skills, though they can be used for Knowledge and
Language skills too." The free `(INT+LOG)*2` pool is spent first; whatever the spend exceeds it by
is `KnowledgeSelection.active_points_used`, drawn from the Skills priority's individual-skill pool.
`create_knowledge_selection` checks it against the Active points the caller says are left, and
`chummer5.engine.skills.create_skill_allocation(knowledge_active_points=)` counts it against the
Skills budget, so whichever step is submitted second sees the first.

**WP125: Karma can buy a new Knowledge/Language skill from rating 0.** A non-native pick may have
rating 0, meaning no points bought it; `create_karma_knowledge_selection` then requires Karma to
raise it to at least 1 (`new Rating x 1`, p. 107: a new one at rating 1 costs 1 Karma).

**WP125: specializations.** p. 148 ("Knowledge Skill Specializations") and p. 150 (Language:
"Specializations: Read/Write, Speak, by dialect, by lingo"). One per skill, as for Active skills
(p. 88). A point-funded one costs 1 free-pool point (p. 88: "A specialization costs 1 skill point");
a Step Seven one costs `chummer5.engine.skills.KARMA_SPECIALIZATION_COST` (7). Both are keyed by the
pick's name, like `KarmaKnowledgeSelection.points`. A native language may be specialized (a native
speaker plainly "has" the skill, p. 129's only precondition); any other pick needs a rating of 1+.

**Native language: one free, cost 0, plus one more per `Bilingual`'s
`ImprovementType.NATIVE_LANGUAGE_LIMIT` bonus** (p. 89-90: "your character receives one language
that he knows as a native language at no cost... If your character has taken the Bilingual quality,
you may have a second native language, which you also receive for free"). A native pick's `rating`
must be exactly `0` -- native fluency isn't a numeric rating at all (the character sheet marks it
"N"), so forcing `0` keeps `points_spent`'s sum correct without a separate "ignore this field"
special case.

**A real fixture-data finding, not a design choice: no fixture in the corpus actually marks a native
language.** Every mundane/magic-capable Priority-built fixture (`Yeti-#ffffff2.chum5`, `Miko.chum5`,
`Wesson.chum5`) predates the legacy engine's own `<isnativelanguage>` field (all three save at
`appversion` 5.202.x, and that field's own "legacy sweep" migration only back-fills newer saves,
`>= 5.212.72` -- see `spec/rulebooks/learnings.md`'s WP49 entry for the full trace). This engine
still models native-language selection correctly (per the rulebook text above); it just can't be
exercised against real corpus data, only hand-verified.

**Cyberware/bioware-boosted INT/LOG do not affect this budget** (p. 95: "Attributes boosted by
cyberware or bioware do not affect the calculation for things such as points for Knowledge skills
or Contacts"). **WP81 makes that real**: `free_knowledge_points` reads
`character.natural_attribute_value(...)`, mirroring `chummer5.engine.resources`'s identical switch
for CHA/contact points. Through WP80 both read the augmented `attribute_value` instead and got away
with it, since nothing in this engine's scope ever produces an `ImprovementType.ATTRIBUTE` bonus
targeting INT or LOG (checked directly: no offered SR5 quality/power/cyberware/bioware item does) --
the distinction still has no observable effect on any buildable character, it is simply no longer
load-bearing that it doesn't.

**WP53 — Step Seven's Karma-funded Knowledge/Language rating increases.** Core rulebook p.106-107,
"KARMA ADVANCEMENT TABLE FOR SKILLS": Knowledge Skills and Language Skills share one row,
`new Rating x 1` per step (confirmed by WP51's own research pass -- see `spec/rulebooks/learnings
.md`'s WP51 entry; both `chummer5.engine.skills`' Active-skill/skill-group Karma formulas and this
one come from the same table). `KarmaKnowledgeSelection` is a separate selection from
`chummer5.engine.skills.KarmaSkillSelection`, not folded into it -- see that module's own WP53
docstring paragraph for why (different catalog, different web-layer route). A pick's *name* (not a
catalog id -- Knowledge/Language skills have none, see this module's own opening paragraph) is what
`karma_points` keys against, resolved against whatever `character.knowledge_selection` already has
committed; native language picks (rating fixed at 0, no numeric rating to raise) are never eligible.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from chummer5.data.knowledge import (
    KNOWLEDGE_CATEGORY_NAMES,
    LANGUAGE_LINKED_ATTRIBUTE,
    knowledge_category,
)
from chummer5.engine.character import Character, karma_advancement_cost
from chummer5.engine.improvements import ImprovementType
from chummer5.engine.skills import (
    KARMA_SPECIALIZATION_COST,
    MAX_SKILL_RATING_CREATE,
    skill_purchase_rules,
)

# Core rulebook p. 89: "Characters receive free Knowledge and Language skills points equal to
# (Intuition rating + Logic rating) x 2."
FREE_POINTS_PER_INT_LOG = 2

# WP53: core rulebook p.106-107, "KARMA ADVANCEMENT TABLE FOR SKILLS" -- Knowledge/Language Skills
# row, `new Rating x 1` (see module docstring's own WP53 paragraph).
KARMA_KNOWLEDGE_PER_RATING = 1

# Core rulebook p. 89-90: one native language is always free; Bilingual raises this by 1 (see
# module docstring). `ImprovementType.NATIVE_LANGUAGE_LIMIT` resolves the Bilingual-granted part;
# this is the fixed base every character gets regardless.
BASE_NATIVE_LANGUAGE_LIMIT = 1

_GLOBAL_TARGET = ""


@dataclass(frozen=True)
class KnowledgeSkillPick:
    """A player-authored Knowledge skill (Academic/Interest/Professional/Street) -- no catalog to
    pick from, mirroring `chummer5.engine.resources.Contact`. `category` must be one of
    `chummer5.data.knowledge.KNOWLEDGE_CATEGORY_NAMES`.
    """

    name: str
    category: str
    rating: int  # WP125: 0 means Karma-bought from scratch


@dataclass(frozen=True)
class LanguageSkillPick:
    """A player-authored Language skill. `native` picks must carry `rating == 0` (see module
    docstring) and don't count against the free-point budget.
    """

    name: str
    rating: int
    native: bool = False


@dataclass(frozen=True)
class KnowledgeSelection:
    """A validated Knowledge/Language spend against the `(INT+LOG)*2` free-point budget."""

    knowledge_skills: tuple[KnowledgeSkillPick, ...]
    languages: tuple[LanguageSkillPick, ...]
    free_points: int
    points_spent: int
    native_language_limit: int
    # WP125: pick name -> specialization, 1 point each (counted in `points_spent`).
    specializations: Mapping[str, str] = MappingProxyType({})
    # WP125: the part of `points_spent` past `free_points`, paid from the Active skill points.
    active_points_used: int = 0


def native_language_limit(character: Character) -> int:
    """`BASE_NATIVE_LANGUAGE_LIMIT` (1) plus whatever `NATIVE_LANGUAGE_LIMIT` Improvements
    (Bilingual, currently the only producer) resolve to."""
    return BASE_NATIVE_LANGUAGE_LIMIT + character.improvements.resolve(
        ImprovementType.NATIVE_LANGUAGE_LIMIT, _GLOBAL_TARGET
    )


def free_knowledge_points(character: Character) -> int:
    """`(Intuition + Logic) * 2` -- see module docstring for the rulebook citation and why
    augmented INT/LOG are excluded.

    **WP81**: reads `natural_attribute_value`, not `attribute_value`, now that the two can differ.
    Core rulebook p. 95 names this calculation specifically ("Attributes boosted by cyberware or
    bioware do not affect the calculation for things such as points for Knowledge skills or
    Contacts"), and legacy's `CharacterSettings.KnowledgeSkillPointsExpression` default says the
    same thing in its own vocabulary: `({INTUnaug} + {LOGUnaug}) * 2`. A no-op for every character
    this engine can build today (nothing in any loaded SR5 catalog augments INT or LOG), but
    correct by construction rather than by that coincidence.
    """
    return (
        character.natural_attribute_value("INT") + character.natural_attribute_value("LOG")
    ) * FREE_POINTS_PER_INT_LOG


def knowledge_dice_pool(character: Character, category: str, rating: int) -> int:
    """Dice pool for a Knowledge skill: `rating + linked attribute` (WP68), where the linked
    attribute (LOG for Academic/Professional, INT for Interest/Street) comes from `category` --
    core rulebook p. 89, "KNOWLEDGE CATEGORY EXAMPLES". Mirrors `chummer5.engine.skills.dice_pool`'s
    unconditional `rating + attribute` core; Knowledge/Language skills carry none of that function's
    specialization/defaulting/group-rating machinery, so this stays a plain sum. Uses the augmented
    `attribute_value` for parity with active skills, though (per this module's own docstring)
    nothing in scope augments INT/LOG.
    """
    linked = knowledge_category(category).linked_attribute
    return character.attribute_value(linked) + rating


def language_dice_pool(character: Character, rating: int) -> int:
    """Dice pool for a Language skill: `rating + Intuition` (WP68) -- every Language skill links to
    INT (core rulebook p. 89, `chummer5.data.knowledge.LANGUAGE_LINKED_ATTRIBUTE`). A native
    language has no numeric rating (fluency "N"), so it has no meaningful dice pool -- callers
    should not invoke this for a native pick.
    """
    return character.attribute_value(LANGUAGE_LINKED_ATTRIBUTE) + rating


def knowledge_points_spent(
    knowledge_skills: Iterable[KnowledgeSkillPick],
    languages: Iterable[LanguageSkillPick],
    specializations: Mapping[str, str] = MappingProxyType({}),
) -> int:
    """Points a Knowledge/Language spend costs: a point per rank, and one per specialization."""
    return (
        sum(pick.rating for pick in knowledge_skills)
        + sum(pick.rating for pick in languages if not pick.native)
        + len(specializations)
    )


@dataclass(frozen=True)
class _NamedPick:
    rating: int
    category: str | None  # None for a language
    native: bool


def _named_picks(
    knowledge_skills: Iterable[KnowledgeSkillPick], languages: Iterable[LanguageSkillPick]
) -> dict[str, list[_NamedPick]]:
    picks: dict[str, list[_NamedPick]] = {}
    for k in knowledge_skills:
        picks.setdefault(k.name, []).append(_NamedPick(k.rating, k.category, False))
    for la in languages:
        picks.setdefault(la.name, []).append(_NamedPick(la.rating, None, la.native))
    return picks


def _resolve_name(picks: Mapping[str, list[_NamedPick]], name: str) -> _NamedPick:
    """The one committed pick called `name`. A name shared by a Knowledge pick and a Language pick
    (each list is only unique within itself) is rejected rather than guessed at."""
    matches = picks.get(name, [])
    if not matches:
        raise ValueError(f"{name!r} is not a committed knowledge/language skill")
    if len(matches) > 1:
        raise ValueError(
            f"{name!r} ambiguously matches more than one committed knowledge/language skill"
        )
    return matches[0]


def _check_specialization(name: str, specialization: str, pick: _NamedPick, rating: int) -> None:
    if not specialization.strip():
        raise ValueError(f"{name!r}: a specialization's name must not be blank")
    if not pick.native and rating < 1:
        raise ValueError(f"{name!r}: cannot add a specialization without at least rating 1")


def create_knowledge_selection(
    character: Character,
    knowledge_skills: Iterable[KnowledgeSkillPick],
    languages: Iterable[LanguageSkillPick],
    specializations: Mapping[str, str] = MappingProxyType({}),
    active_points_available: int = 0,
) -> KnowledgeSelection:
    """Build a `KnowledgeSelection`, validating names/categories/ratings and the point budget.

    Does not require the full budget to be spent (see module docstring).

    **WP125**: a non-native pick may be rated 0 (Karma will buy it). `specializations` (pick name
    -> name) costs a point each; its pick must be rated 1+ or native. A spend past the free pool
    draws on `active_points_available`, the Active skill points the Skills step left unspent.
    """
    knowledge_t = tuple(knowledge_skills)
    languages_t = tuple(languages)

    seen_knowledge_names: set[str] = set()
    for pick in knowledge_t:
        name = pick.name.strip()
        if not name:
            raise ValueError("a knowledge skill's name must not be blank")
        if name in seen_knowledge_names:
            raise ValueError(f"duplicate knowledge skill name: {name!r}")
        seen_knowledge_names.add(name)
        if pick.category not in KNOWLEDGE_CATEGORY_NAMES:
            raise ValueError(
                f"{name}: not a knowledge-skill category: {pick.category!r} (expected one of "
                f"{KNOWLEDGE_CATEGORY_NAMES})"
            )
        if not 0 <= pick.rating <= MAX_SKILL_RATING_CREATE:
            raise ValueError(
                f"{name}: rating must be between 0 and {MAX_SKILL_RATING_CREATE}, got {pick.rating}"
            )

    seen_language_names: set[str] = set()
    native_count = 0
    for language_pick in languages_t:
        name = language_pick.name.strip()
        if not name:
            raise ValueError("a language skill's name must not be blank")
        if name in seen_language_names:
            raise ValueError(f"duplicate language skill name: {name!r}")
        seen_language_names.add(name)
        if language_pick.native:
            native_count += 1
            if language_pick.rating != 0:
                raise ValueError(
                    f"{name}: a native language's rating must be 0, got {language_pick.rating}"
                )
        elif not 0 <= language_pick.rating <= MAX_SKILL_RATING_CREATE:
            raise ValueError(
                f"{name}: rating must be between 0 and {MAX_SKILL_RATING_CREATE}, got "
                f"{language_pick.rating}"
            )

    limit = native_language_limit(character)
    if native_count > limit:
        raise ValueError(f"at most {limit} language(s) may be marked native, got {native_count}")

    picks = _named_picks(knowledge_t, languages_t)
    for name, specialization in specializations.items():
        named = _resolve_name(picks, name)
        _check_specialization(name, specialization, named, named.rating)

    free_points = free_knowledge_points(character)
    points_spent = knowledge_points_spent(knowledge_t, languages_t, specializations)
    active_points_used = max(0, points_spent - free_points)
    if active_points_used > active_points_available:
        raise ValueError(
            f"knowledge/language point spend {points_spent} exceeds the free budget of "
            f"{free_points} plus the {active_points_available} Active skill point(s) left"
        )

    return KnowledgeSelection(
        knowledge_skills=knowledge_t,
        languages=languages_t,
        free_points=free_points,
        points_spent=points_spent,
        native_language_limit=limit,
        specializations=MappingProxyType(dict(specializations)),
        active_points_used=active_points_used,
    )


@dataclass(frozen=True)
class KarmaKnowledgeSelection:
    """Leftover-Karma-funded Knowledge/Language rating increases (Step Seven, WP53) -- see
    `create_karma_knowledge_selection`'s own docstring for the validation this wraps.

    `points` is keyed by pick *name* (not a catalog id -- see module docstring), resolved against
    whatever `character.knowledge_selection` already has committed. Always the full resulting
    state, not an incremental delta -- the same "recompute wholesale" shape
    `KarmaAttributeSelection`/`KarmaSkillSelection` already established. WP125 adds
    `specializations`, name -> specialization, 7 Karma each.
    """

    points: MappingProxyType[str, int]
    karma_cost: int
    specializations: Mapping[str, str] = MappingProxyType({})


def create_karma_knowledge_selection(
    character: Character,
    karma_points: Mapping[str, int],
    karma_budget: int,
    karma_specializations: Mapping[str, str] = MappingProxyType({}),
) -> KarmaKnowledgeSelection:
    """Validate and build a `KarmaKnowledgeSelection`.

    `karma_points` raises a committed, non-native Knowledge or Language pick's rating (looked up by
    name against `character.knowledge_selection.knowledge_skills`/`.languages`) at `new Rating x 1`
    Karma per rating step, cumulative (see module docstring's WP53 paragraph).

    Validates: every key names a committed, non-native Knowledge/Language pick (unambiguously --
    a name shared between a Knowledge pick and a Language pick, which `create_knowledge_selection`
    itself never rejects since it checks each list's names for uniqueness separately, is rejected
    here rather than guessed at); no negative spend; the resulting rating does not exceed
    `MAX_SKILL_RATING_CREATE`; and the total Karma cost does not exceed `karma_budget` (the
    caller's responsibility to derive -- typically `character.karma_remaining + <this selection's
    own currently-committed karma_cost>`, mirroring every other Karma-spending `create_*`
    function's `karma_budget` parameter).

    **WP117**: a knowledge skill's cost is raised by its category's Karma cost percent -- Uneducated
    doubles Academic and Professional knowledge (p. 87). Languages have no category.

    **WP125**: a pick committed at rating 0 must be raised to 1+ here -- that is Karma buying a
    new skill. `karma_specializations` buys a specialization for 7 Karma (the same Uneducated
    percent applies, as for Active skills); the pick must not already have a point-funded one, and
    must be native or rated 1+ after this selection's Karma.
    """
    knowledge_selection = character.knowledge_selection
    cost_percent = skill_purchase_rules(character).karma_cost_percent
    specialization_percent = skill_purchase_rules(character).specialization_karma_cost_percent
    picks = (
        _named_picks(knowledge_selection.knowledge_skills, knowledge_selection.languages)
        if knowledge_selection is not None
        else {}
    )
    existing_specializations = (
        knowledge_selection.specializations if knowledge_selection is not None else {}
    )

    def _with_percent(amount: int, category: str | None, percents: Mapping[str, int]) -> int:
        percent = percents.get(category, 0) if category is not None else 0
        return (amount * (100 + percent) + 50) // 100

    nonzero_points = MappingProxyType({name: pts for name, pts in karma_points.items() if pts})
    cost = 0
    for name, points in nonzero_points.items():
        if points < 0:
            raise ValueError(f"{name!r}: Karma-funded points must not be negative, got {points}")
        pick = _resolve_name(picks, name)
        if pick.native:
            raise ValueError(f"{name!r} is not a committed, non-native knowledge/language skill")
        total = pick.rating + points
        if total > MAX_SKILL_RATING_CREATE:
            raise ValueError(
                f"{name!r}: {total} exceeds the chargen skill rating maximum of "
                f"{MAX_SKILL_RATING_CREATE}"
            )
        step_cost = karma_advancement_cost(pick.rating, points, KARMA_KNOWLEDGE_PER_RATING)
        cost += _with_percent(step_cost, pick.category, cost_percent)

    for name, name_picks in picks.items():
        for pick in name_picks:
            if not pick.native and pick.rating == 0 and nonzero_points.get(name, 0) == 0:
                raise ValueError(
                    f"{name!r}: a knowledge/language skill at rating 0 needs Karma to buy it"
                )

    for name, specialization in karma_specializations.items():
        pick = _resolve_name(picks, name)
        if name in existing_specializations:
            raise ValueError(
                f"{name!r}: already has a specialization ({existing_specializations[name]!r})"
            )
        _check_specialization(name, specialization, pick, pick.rating + nonzero_points.get(name, 0))
        cost += _with_percent(KARMA_SPECIALIZATION_COST, pick.category, specialization_percent)

    if cost > karma_budget:
        raise ValueError(
            f"Karma-funded knowledge/language spend {cost} exceeds the Karma budget of "
            f"{karma_budget}"
        )

    return KarmaKnowledgeSelection(
        points=nonzero_points,
        karma_cost=cost,
        specializations=MappingProxyType(dict(karma_specializations)),
    )
