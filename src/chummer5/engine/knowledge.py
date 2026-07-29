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

**Deliberately not modeled: Active-skill points funding Knowledge/Language spend.** The rulebook
allows unspent Active-skill priority points to be redirected into Knowledge/Language ("These skill
points are generally used to purchase Active skills, though they can be used for Knowledge and
Language skills too," p. 88) -- this WP only implements the separate, unconditional `(INT+LOG)*2`
free-point pool every character gets regardless, not that cross-funding path. A real, deliberate
scope cut (mirrors `chummer5.engine.skills`'s own "Karma-bought skill points are out of scope" cut),
not an oversight.

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

**Cyberware/bioware-boosted INT/LOG do not affect this budget** (p. 90: "Cyberware/bioware-boosted
attributes do not affect Knowledge-skill-point or Contact-point formulas"). `character.attribute_
value(...)` is used directly anyway, mirroring `chummer5.engine.resources`'s identical choice for
CHA/contact points -- nothing in this engine's current scope ever produces an `ImprovementType
.ATTRIBUTE` bonus targeting INT or LOG (checked directly: no offered SR5 quality/power/cyberware/
bioware item does), so the distinction has no observable effect yet, the same "real rule, currently
unobservable" note `chummer5.engine.resources`'s own docstring already makes for CHA.

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
from chummer5.engine.skills import MAX_SKILL_RATING_CREATE

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
    rating: int


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


def native_language_limit(character: Character) -> int:
    """`BASE_NATIVE_LANGUAGE_LIMIT` (1) plus whatever `NATIVE_LANGUAGE_LIMIT` Improvements
    (Bilingual, currently the only producer) resolve to."""
    return BASE_NATIVE_LANGUAGE_LIMIT + character.improvements.resolve(
        ImprovementType.NATIVE_LANGUAGE_LIMIT, _GLOBAL_TARGET
    )


def free_knowledge_points(character: Character) -> int:
    """`(Intuition + Logic) * 2` -- see module docstring for the rulebook citation and why
    augmented INT/LOG (were anything in this engine's scope to produce one) would be excluded.
    """
    return (
        character.attribute_value("INT") + character.attribute_value("LOG")
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


def create_knowledge_selection(
    character: Character,
    knowledge_skills: Iterable[KnowledgeSkillPick],
    languages: Iterable[LanguageSkillPick],
) -> KnowledgeSelection:
    """Build a `KnowledgeSelection`, validating names/categories/ratings and the free-point budget.

    Does not require the full budget to be spent (see module docstring).
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
        if not 1 <= pick.rating <= MAX_SKILL_RATING_CREATE:
            raise ValueError(
                f"{name}: rating must be between 1 and {MAX_SKILL_RATING_CREATE}, got {pick.rating}"
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
        elif not 1 <= language_pick.rating <= MAX_SKILL_RATING_CREATE:
            raise ValueError(
                f"{name}: rating must be between 1 and {MAX_SKILL_RATING_CREATE}, got "
                f"{language_pick.rating}"
            )

    limit = native_language_limit(character)
    if native_count > limit:
        raise ValueError(f"at most {limit} language(s) may be marked native, got {native_count}")

    free_points = free_knowledge_points(character)
    points_spent = sum(pick.rating for pick in knowledge_t) + sum(
        pick.rating for pick in languages_t if not pick.native
    )
    if points_spent > free_points:
        raise ValueError(
            f"knowledge/language point spend {points_spent} exceeds the free budget of "
            f"{free_points}"
        )

    return KnowledgeSelection(
        knowledge_skills=knowledge_t,
        languages=languages_t,
        free_points=free_points,
        points_spent=points_spent,
        native_language_limit=limit,
    )


@dataclass(frozen=True)
class KarmaKnowledgeSelection:
    """Leftover-Karma-funded Knowledge/Language rating increases (Step Seven, WP53) -- see
    `create_karma_knowledge_selection`'s own docstring for the validation this wraps.

    `points` is keyed by pick *name* (not a catalog id -- see module docstring), resolved against
    whatever `character.knowledge_selection` already has committed. Always the full resulting
    state, not an incremental delta -- the same "recompute wholesale" shape
    `KarmaAttributeSelection`/`KarmaSkillSelection` already established.
    """

    points: MappingProxyType[str, int]
    karma_cost: int


def create_karma_knowledge_selection(
    character: Character, karma_points: Mapping[str, int], karma_budget: int
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
    """
    knowledge_selection = character.knowledge_selection

    def _current_rating(name: str) -> int:
        if knowledge_selection is None:
            raise ValueError(f"{name!r} is not a committed knowledge/language skill")
        matches = [p.rating for p in knowledge_selection.knowledge_skills if p.name == name]
        matches += [
            p.rating for p in knowledge_selection.languages if p.name == name and not p.native
        ]
        if not matches:
            raise ValueError(f"{name!r} is not a committed, non-native knowledge/language skill")
        if len(matches) > 1:
            raise ValueError(
                f"{name!r} ambiguously matches more than one committed knowledge/language skill"
            )
        return matches[0]

    nonzero_points = MappingProxyType({name: pts for name, pts in karma_points.items() if pts})
    cost = 0
    for name, points in nonzero_points.items():
        if points < 0:
            raise ValueError(f"{name!r}: Karma-funded points must not be negative, got {points}")
        start_rating = _current_rating(name)
        total = start_rating + points
        if total > MAX_SKILL_RATING_CREATE:
            raise ValueError(
                f"{name!r}: {total} exceeds the chargen skill rating maximum of "
                f"{MAX_SKILL_RATING_CREATE}"
            )
        cost += karma_advancement_cost(start_rating, points, KARMA_KNOWLEDGE_PER_RATING)

    if cost > karma_budget:
        raise ValueError(
            f"Karma-funded knowledge/language spend {cost} exceeds the Karma budget of "
            f"{karma_budget}"
        )

    return KarmaKnowledgeSelection(points=nonzero_points, karma_cost=cost)
