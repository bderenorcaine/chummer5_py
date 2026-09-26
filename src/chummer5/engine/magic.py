"""Magic-type, Magic-rating, tradition, and the Talent free-skill grant (Phase I, WP25).

Composes WP24's real Talent-letter plumbing with WP2's Talent priority data
(`chummer5.data.priorities`), the new SR5-tradition catalog (`chummer5.data.traditions`), and WP7's
skill catalog (`chummer5.data.skills`) into a buildable Magic-type + Magic-rating + tradition +
free-skill selection. Mundane/Magician/Adept only — Mystic Adept/Technomancer/A.I./Aspected
Magician/Apprentice/Explorer/Enchanter/Aware are all excluded, per the explicit scope cuts recorded
in the Implementation Plan's Phase I intro.

**The one finding this module must not miscopy from `chummer5.engine.character`'s EDG precedent:
Magic rating is not a point-buy.** Every other attribute is `metatype minimum + points spent + Σ
improvements`, funded from a priority-derived budget. Magic works differently: the chosen Talent
option's `magic` field (`chummer5.data.priorities.TalentOption.magic`) *is* the finished MAG rating
outright, confirmed against both of this phase's real fixtures (Miko: Talent A/Magician grants "6
Magic", her own MAG totalvalue is exactly 6; Wesson: Talent C/Adept grants "4 Magic", his MAG
totalvalue is exactly 4). See `spec/worklogs/WP25.md` for the full research, including a correction
to the Implementation Plan's own "Adept letter B grants a free skill, C/D don't" claim -- letter C
does too, confirmed both in `priorities.xml` and in Wesson's own `.chum5` (`<priorityskills>`
records his grant as `Pistols`).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from chummer5.data.powers import BonusSupport as PowerBonusSupport
from chummer5.data.powers import Power
from chummer5.data.priorities import PriorityTable, TalentOption
from chummer5.data.skills import Skill, load_skills
from chummer5.data.spells import Spell
from chummer5.data.traditions import Tradition
from chummer5.engine.character import Character
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType
from chummer5.engine.skills import natural_skill_rating

# This phase's offered subset of each Talent letter's real option list (Implementation Plan's Phase
# I intro): Mystic Adept (explicit product decision, not deferred) and Technomancer/A.I./Aspected
# Magician/Apprentice/Explorer/Enchanter/Aware (each a real archetype with its own restricted-access
# rules neither of this phase's two fixtures exercises) are all excluded. "Mundane" is included so a
# player assigning Talent a letter that happens to offer it can still choose it -- none of A-D
# currently do (every option at those letters is a real archetype; only E offers "Mundane" -- see
# `chummer5.data.priorities.PriorityTable.mundane_talent`), but this module doesn't hardcode that,
# it just restricts to the *name*.
OFFERED_TALENT_CODENAMES = ("Mundane", "Magician", "Adept")

# Talent's `skilltype = "magic"` grant (Magician, every letter that grants one): traced directly
# from `SelectMetatypePriority.cs`'s `GetMagicalSkillList()`, confirmed verbatim as
# `skills/skill[category = "Magical Active" or category = "Pseudo-Magical Active"]` -- a plain
# filter over `Skill.category`. See Implementation Plan's Phase I intro.
# WP61: also reused (not re-derived) by `chummer5.web.app` to widen the Skills-priority *buy* UI
# for a magic-active character -- public (no leading underscore) for that cross-module reuse.
MAGICAL_SKILL_CATEGORIES = frozenset({"Magical Active", "Pseudo-Magical Active"})


def _xpath_grant_eligible(skill: Skill) -> bool:
    """Talent's `skilltype = "xpath"` grant (Adept, letters B and C both carry it): the one literal
    XPath expression this phase's offered options ever produce, confirmed verbatim against
    `priorities.xml`: `not(attribute = 'RES' or attribute = 'DEP') and (not(category = 'Magical
    Active') or skillgroup = '' or not(skillgroup))` -- any active skill not linked to RES/DEP,
    excluding Magical Active skills that belong to a skill group. See Implementation Plan's Phase I
    intro for why this is recognized as one named, hardcoded predicate rather than a general XPath
    evaluator.
    """
    return skill.attribute not in {"RES", "DEP"} and (
        skill.category != "Magical Active" or not skill.skill_group
    )


@dataclass(frozen=True)
class MagicSelection:
    """A validated Magic-type + Magic-rating + tradition + free-skill-grant choice.

    Exists as `create_magic_selection`'s return value, not a field `Character` stores wholesale --
    a caller unpacks it onto `Character`'s own flat `magic_type`/`magic_rating`/`tradition`/
    `magic_granted_skill_ids` fields via `dataclasses.replace` (mirrors `MetatypeChoice`'s own
    relationship to `Character.metatype`/`heritage_letter`; see that class's docstring).
    """

    magic_type: str | None  # "Magician"/"Adept"; None for Mundane
    magic_rating: int  # 0 for Mundane
    tradition: Tradition | None  # Magician only
    granted_skill_ids: tuple[str, ...]  # () for Mundane or a no-grant letter/codename
    granted_skill_rating: int  # 0 when granted_skill_ids is empty


def offered_talent_options(letter: str, priorities: PriorityTable) -> tuple[TalentOption, ...]:
    """One Talent letter's real option list, restricted to this phase's offered codenames."""
    return tuple(
        option
        for option in priorities.talent[letter].options
        if option.codename in OFFERED_TALENT_CODENAMES
    )


def magic_skill_grant_eligible_skills(
    talent_option: TalentOption, skills: Iterable[Skill]
) -> tuple[Skill, ...]:
    """Which skills `talent_option`'s free-skill grant may be spent on, dispatching on
    `skill_type`. `talent_option.skill_type is None` (an option with no grant at all, e.g. Adept
    letter D or Magician letter C) has nothing eligible.

    Raises `ValueError` for a `skill_type` this phase doesn't recognize -- a genuinely different
    value would mean a Talent option this phase's traced predicates don't cover is somehow being
    offered; see the Implementation Plan's Phase I intro for why a general XPath evaluator isn't
    built for this instead.
    """
    if talent_option.skill_type is None:
        return ()
    if talent_option.skill_type == "magic":
        return tuple(s for s in skills if s.category in MAGICAL_SKILL_CATEGORIES)
    if talent_option.skill_type == "xpath":
        return tuple(s for s in skills if _xpath_grant_eligible(s))
    raise ValueError(f"unrecognized Talent skill_type: {talent_option.skill_type!r}")


def create_magic_selection(
    talent_letter: str,
    talent_codename: str,
    tradition_id: str | None,
    granted_skill_ids: Iterable[str],
    priorities: PriorityTable,
    traditions: Iterable[Tradition],
    skills: Iterable[Skill],
) -> MagicSelection:
    """Build a `MagicSelection`, validating the codename/tradition/free-skill-grant together.

    Validates: `talent_codename` is one of `talent_letter`'s real, phase-offered options (`offered_
    talent_options`); Magician requires a `tradition_id` resolving to one of `traditions`'s 2
    entries, Adept/Mundane forbid one; the free-skill grant picks exactly the matched option's
    `skill_qty` distinct ids, each eligible per `magic_skill_grant_eligible_skills` -- Mundane or a
    no-grant option forbids any picks at all. Does not touch `chummer5.engine.skills
    .SkillAllocation` or its budget -- see `apply_magic_skill_grant_improvements` for how the grant
    still reaches a skill's real total rating without double-counting against that budget.
    """
    offered = {opt.codename: opt for opt in offered_talent_options(talent_letter, priorities)}
    option = offered.get(talent_codename)
    if option is None:
        raise ValueError(
            f"{talent_codename!r} is not an offered Talent option at letter {talent_letter!r}"
        )

    skill_ids = list(granted_skill_ids)

    if option.codename == "Mundane":
        if tradition_id is not None:
            raise ValueError("Mundane cannot choose a tradition")
        if skill_ids:
            raise ValueError("Mundane receives no Talent free-skill grant")
        return MagicSelection(
            magic_type=None,
            magic_rating=0,
            tradition=None,
            granted_skill_ids=(),
            granted_skill_rating=0,
        )

    if option.magic is None:
        raise ValueError(f"{talent_codename!r} at letter {talent_letter!r} has no Magic rating")
    magic_rating = option.magic

    tradition: Tradition | None = None
    if option.codename == "Magician":
        if tradition_id is None:
            raise ValueError("Magician requires a tradition")
        tradition = next((t for t in traditions if t.id == tradition_id), None)
        if tradition is None:
            raise ValueError(f"not an offered tradition id: {tradition_id!r}")
    elif tradition_id is not None:
        raise ValueError(f"{talent_codename!r} cannot choose a tradition")

    if option.skill_qty is None:
        if skill_ids:
            raise ValueError(
                f"{talent_codename!r} at letter {talent_letter!r} grants no free skill"
            )
        return MagicSelection(
            magic_type=option.codename,
            magic_rating=magic_rating,
            tradition=tradition,
            granted_skill_ids=(),
            granted_skill_rating=0,
        )

    eligible_ids = {s.id for s in magic_skill_grant_eligible_skills(option, skills)}
    unknown = sorted(set(skill_ids) - eligible_ids)
    if unknown:
        raise ValueError(f"not eligible for the Talent free-skill grant: {unknown}")
    duplicates = sorted({sid for sid in skill_ids if skill_ids.count(sid) > 1})
    if duplicates:
        raise ValueError(
            f"skill selected more than once for the Talent free-skill grant: {duplicates}"
        )
    if len(skill_ids) != option.skill_qty:
        raise ValueError(
            f"{talent_codename!r} at letter {talent_letter!r} grants exactly {option.skill_qty} "
            f"free skill(s), got {len(skill_ids)}"
        )

    return MagicSelection(
        magic_type=option.codename,
        magic_rating=magic_rating,
        tradition=tradition,
        granted_skill_ids=tuple(skill_ids),
        granted_skill_rating=option.skill_val or 0,
    )


def create_magic_attribute_points(
    magic_type: str | None,
    points: int,
    magic_rating: int,
    magic_maximum: int,
    special_attribute_points_budget: int,
    other_special_attribute_points_spent: int,
) -> int:
    """Validate `points` spent raising Magic (or Resonance -- not modeled, RES stays out of scope
    entirely per the Project Overview) beyond the Talent-granted starting rating.

    **Correction to this module's own earlier finding.** WP25's docstring claimed "the Magic rating
    is not a point-buy" -- true that it isn't funded from the *Attributes*-priority budget the
    primary 8 attributes use, but wrong that it can't be raised at all. Core rulebook p.65 ("Choose
    Metatype" -> "Special Attributes"): "[Special attribute points] may be spent entirely on Edge
    if the player chooses not to play a magic user or a technomancer, or they may split these
    points as they see fit between their Edge and Magic or Resonance attribute ratings if the
    player so chooses" -- confirmed both in the rulebook's own worked examples (p.69-70, a
    Magic/Resonance row with its own "Points Spent" column right alongside Edge's) and in the
    legacy `SelectMetatypePriority.cs`'s "Set starting magic" block, which sets MAG's *minimum* to
    the Talent option's `magic` field via the exact same `AssignLimits` mechanism every other
    attribute uses, not a fixed final value. See `spec/rulebooks/learnings.md`'s "Post-WP29
    correction" entry for the full citations.

    `points` is spent from the **same** Heritage-derived special-attribute-points pool
    `create_character` already validates EDG against -- `other_special_attribute_points_spent` is
    the caller's responsibility to resolve (typically `character.attribute_points.get("EDG", 0)`),
    mirroring how `create_resources_selection`/`create_lifestyle_selection` each take the other
    selection's own cost to validate one shared budget jointly (see `chummer5.engine.lifestyle`'s
    module docstring for that precedent). A Mundane character (`magic_type is None`) can never
    spend any points here at all -- MAG isn't merely zero for Mundane, it's not an allocatable
    attribute in the first place (mirrors the legacy `MAGEnabled` flag, granted only by the
    Magician/Adept quality's own `<enableattribute>` bonus).
    """
    if magic_type is None:
        if points != 0:
            raise ValueError(
                "Magic is not allocatable without a confirmed magic-active Talent selection"
            )
        return 0
    if points < 0:
        raise ValueError(f"points spent must not be negative, got {points}")
    if magic_rating + points > magic_maximum:
        raise ValueError(
            f"Magic {magic_rating + points} would exceed the metatype's Magic maximum of "
            f"{magic_maximum}"
        )
    total_special_spent = other_special_attribute_points_spent + points
    if total_special_spent > special_attribute_points_budget:
        raise ValueError(
            f"special attribute spend {total_special_spent} (Edge + Magic combined) exceeds the "
            f"special-attribute-points budget of {special_attribute_points_budget}"
        )
    return points


# One shared source_id for every skill a single character's Talent grant touches, so a later Talent
# change can retract the whole grant in one `ImprovementIndex.remove_source` call (mirrors
# `chummer5.engine.qualities`'s per-quality `source_id`, just at the grant's own granularity since
# there's only ever one grant per character, not one per skill).
MAGIC_SKILL_GRANT_SOURCE_ID = "magic_skill_grant"


def apply_magic_skill_grant_improvements(
    character: Character, selection: MagicSelection, skills: Iterable[Skill]
) -> None:
    """Add the Talent free-skill grant's rating as `Improvement`s targeting each granted skill.

    Reuses `ImprovementType.SKILL`, the exact mechanism `chummer5.engine.qualities` already
    established for flat skill bonuses (targets a skill by name; `chummer5.engine.skills
    .skill_rating`'s existing `points + Σ improvements` formula already sums it in). This
    deliberately does **not** touch `SkillAllocation` or its budget: the grant isn't bought with
    Skills-priority points, so it must never be validated against that budget -- but it still needs
    to show up in the skill's real total rating, which routing it through `ImprovementIndex`
    (rather than, say, a second field on `SkillAllocation`) gets for free, no new formula needed.
    """
    by_id = {s.id: s for s in skills}
    for skill_id in selection.granted_skill_ids:
        character.improvements.add(
            Improvement(
                improvement_type=ImprovementType.SKILL,
                target=by_id[skill_id].name,
                value=selection.granted_skill_rating,
                source_type=ImprovementSource.TALENT,
                source_id=MAGIC_SKILL_GRANT_SOURCE_ID,
            )
        )


# WP54: core rulebook p.98, "Additional Purchases & Restrictions" table -- "Spells -- Karma Cost
# (at character creation): 5 Karma per spell -- Restriction: Maximum number of spells/rituals/
# preparations known at Character Creation equals Magic Rating x 2." Re-extracted directly via
# `pdftotext -layout` (see spec/rulebooks/learnings.md's WP54 entry), not trusted from the
# Implementation Plan's own secondhand transcription.
KARMA_PER_SPELL = 5


@dataclass(frozen=True)
class SpellSelection:
    """A validated set of spells picked against a Magician's Talent-option spell budget (WP26),
    widened by WP54 to allow leftover Karma to buy spells beyond that free budget.

    `budget` is carried alongside `spells` (rather than left for a caller to re-derive) so a render
    can show "N of budget spells chosen" without re-looking-up the Talent option. There is no
    equivalent `apply_*_improvements` function for spells, unlike qualities/the Talent skill grant
    -- per the module docstring, a spell has no chargen-time computed effect to apply; it is purely
    a roster entry.

    **WP54**: `karma_spell_count`/`karma_cost` -- how many of `spells` are Karma-funded (beyond the
    free `budget`) and their total Karma cost (`karma_spell_count * KARMA_PER_SPELL`). Which
    *specific* spells count as "free" vs. "Karma-funded" is never tracked -- every spell is
    mechanically identical once known, so only the *count* beyond `budget` matters for cost/cap
    purposes (mirrors `create_karma_attribute_points`'s own "the selection is a validated total,
    not a per-item ledger of which points came from which pool" shape).
    """

    spells: tuple[Spell, ...]
    budget: int
    karma_spell_count: int
    karma_cost: int


def create_spell_selection(
    spell_ids: Iterable[str],
    catalog: Iterable[Spell],
    budget: int,
    magic_rating: int,
    karma_budget: int,
) -> SpellSelection:
    """Build a `SpellSelection`, validating against `catalog`, `budget`, the "Magic Rating x 2"
    known-spells cap, and `karma_budget` together.

    Validates: every id resolves against `catalog` (the SR5-scoped spell list --
    `chummer5.data.spells.load_spells()`); no spell is picked more than once; the total picked
    doesn't exceed `magic_rating * 2` (the rulebook's own combined free-plus-Karma-funded cap, p.98
    -- see `KARMA_PER_SPELL`'s own citation); and the Karma cost of whatever's picked beyond
    `budget` (`max(0, len(spell_ids) - budget) * KARMA_PER_SPELL`) doesn't exceed `karma_budget`.

    `budget`/`magic_rating`/`karma_budget` are all the caller's responsibility to resolve correctly
    -- `budget` a Magician's chosen Talent option's `spells` field (see
    `chummer5.data.priorities.TalentOption.spells`) or 0 for Adept/Mundane, which never have one;
    `magic_rating` the character's *finished* Magic rating (`character.attribute_value("MAG")`,
    post-Essence-loss); `karma_budget` typically `character.karma_remaining` plus this selection's
    own currently-committed `karma_cost`, mirroring every other Karma-spending `create_*` function's
    "exclude this section's own prior commitment" idiom. This function has no `magic_type`
    parameter of its own -- passing `budget=0, magic_rating=0` (the Adept/Mundane case) already
    rejects any pick via the Magic-Rating-x-2 cap (which is 0), so there's nothing else to check for
    that case specifically.
    """
    ids = list(spell_ids)
    by_id = {s.id: s for s in catalog}

    unknown = sorted({sid for sid in ids if sid not in by_id})
    if unknown:
        raise ValueError(f"not an SR5-scoped spell id: {unknown}")

    duplicates = sorted({sid for sid in ids if ids.count(sid) > 1})
    if duplicates:
        raise ValueError(f"spell selected more than once: {duplicates}")

    max_known = magic_rating * 2
    if len(ids) > max_known:
        raise ValueError(
            f"{len(ids)} spells known, exceeding the Magic Rating x2 cap of {max_known}"
        )

    karma_spell_count = max(0, len(ids) - budget)
    karma_cost = karma_spell_count * KARMA_PER_SPELL
    if karma_cost > karma_budget:
        raise ValueError(
            f"{karma_cost} Karma spent on {karma_spell_count} spell(s) beyond the free budget of "
            f"{budget}, exceeding the Karma budget of {karma_budget}"
        )

    return SpellSelection(
        spells=tuple(by_id[sid] for sid in ids),
        budget=budget,
        karma_spell_count=karma_spell_count,
        karma_cost=karma_cost,
    )


# -- Adept powers (WP27) ---------------------------------------------------------------------

_POWER_TARGET_KIND_TO_IMPROVEMENT_TYPE = {
    "skill": ImprovementType.SKILL,
    "select_attribute": ImprovementType.ATTRIBUTE,
    "mental_limit": ImprovementType.MENTAL_LIMIT,
    "physical_limit": ImprovementType.PHYSICAL_LIMIT,
    "social_limit": ImprovementType.SOCIAL_LIMIT,
    # WP118: Astral Perception.
    "unlock_skill": ImprovementType.SKILL_UNLOCKED,
    # WP119: Improved Reflexes, Mystic Armor, Pain Resistance.
    "attribute": ImprovementType.ATTRIBUTE,
    "initiative_dice": ImprovementType.INITIATIVE_DICE,
    "armor": ImprovementType.ARMOR,
    "cm_threshold_offset": ImprovementType.CM_THRESHOLD_OFFSET,
}

# WP119: NO_EFFECT powers (in play only, with a note) are offered too, like NO_EFFECT qualities.
_OFFERABLE_POWER_SUPPORT = (PowerBonusSupport.FLAT_BONUS, PowerBonusSupport.NO_EFFECT)

# WP119: what a skill-targeted power's categories resolve against.
_SKILLS = load_skills()


def mvp_power_catalog(powers: Iterable[Power]) -> tuple[Power, ...]:
    """Restrict a power catalog to the ones MVP can actually offer a player to buy.

    Mirrors `chummer5.engine.qualities.mvp_quality_catalog`: `chummer5.data.powers.load_powers()`
    already restricts to `source == "SR5"`; this narrows further to `BonusSupport.FLAT_BONUS` (a
    bonus shape this engine's Improvement mechanism can apply correctly) and, since WP119,
    `NO_EFFECT` (an in-play power offered with its registry note). A `NOT_YET_SUPPORTED` power is
    excluded entirely rather than offered with its mechanical effect silently dropped.
    """
    return tuple(p for p in powers if p.bonus_support in _OFFERABLE_POWER_SUPPORT)


@dataclass(frozen=True)
class PowerPick:
    """One purchased Adept Power instance: which power, at what rating, and -- for a power that
    names something (`Power.target_kind`) -- which attribute or skill (WP119; WP27's
    `selected_attribute`, widened). Critical Strike bought for Blades and for Unarmed Combat is two
    picks."""

    power: Power
    rating: int
    target: str | None = None

    @property
    def power_points(self) -> Decimal:
        """`points x rating + extra_point_cost` (WP119: Improved Reflexes' +0.5)."""
        return self.power.points * self.rating + self.power.extra_point_cost


@dataclass(frozen=True)
class PowerSelection:
    """A validated set of Adept Power purchases and their total Power Point cost.

    `power_points_spent` is a `Decimal`, not an `int` -- SR5 Power Point costs are routinely
    fractional (0.25, 0.5, 1 all appear among the FLAT_BONUS candidates below), the same
    fractional-value question the Implementation Plan's Phase J/WP30 flags for Essence. Scoped
    locally to this one selection's own budget arithmetic rather than widening `Improvement.value`
    engine-wide -- a purchased power's *bonus* value (fed into `Improvement.value` by
    `apply_power_improvements` below) is always a plain int (the purchased rating), so nothing
    about `Improvement` itself needs to change for this WP; WP30 is where the engine-wide question,
    if any, actually gets decided.
    """

    picks: tuple[PowerPick, ...]
    power_points_spent: Decimal
    power_point_budget: int


def power_target_options(power: Power, skills: Iterable[Skill] = _SKILLS) -> tuple[str, ...]:
    """Every value a pick of `power` may name in `target` (WP119), or `()` for a power that names
    nothing or takes free text."""
    if power.target_kind == "attribute":
        return power.target_options
    if power.target_kind == "skill":
        if power.target_options:
            return power.target_options
        return tuple(
            sorted(
                s.name
                for s in skills
                if s.category in power.target_skill_categories
                and s.name not in power.target_excluded
            )
        )
    return ()


def _boosts_target_rating(power: Power) -> bool:
    """Improved Ability's shape: a `skill` bonus to the pick's own target."""
    return any(b.target_kind == "skill" and not b.target_name for b in power.flat_bonuses)


def power_max_rating(power: Power, magic_rating: int, learned_rating: int | None = None) -> int:
    """The highest level of `power` a character may hold (WP119).

    p. 308: "The maximum number of levels you can have of any one power is equal to your Magic
    Rating, or up to a limit listed by the power, whichever is less" -- the power's limit is its
    `<maxlevels>` (Improved Reflexes' 3). A power without levels is 1. Improved Ability is also
    capped by its skill: "The maximum improvement possible is your current skill level x 1.5
    (rounded up)" (p. 309), which legacy's default reads as at most half the learned rating,
    rounded up, on top of it -- `learned_rating` is that rating, when known.
    """
    if not power.levels:
        return 1
    cap = magic_rating
    if power.max_levels:
        cap = min(cap, power.max_levels)
    if learned_rating is not None and _boosts_target_rating(power):
        cap = min(cap, -(-learned_rating // 2))
    return cap


def learned_skill_ratings(character: Character, skills: Iterable[Skill]) -> dict[str, int]:
    """Each skill's learned rating, by name (WP119): what was bought for it, plus the Talent's free
    skill grant -- which legacy counts as bought and this engine routes through a `TALENT`
    Improvement (WP25). No other Improvement counts, Improved Ability's own included, so the power
    can't lift its own cap."""
    allocation = character.skill_allocation
    granted: dict[str, int] = {}
    for imp in character.improvements.improvements:
        if imp.improvement_type is ImprovementType.SKILL and imp.source_type is (
            ImprovementSource.TALENT
        ):
            granted[imp.target] = granted.get(imp.target, 0) + imp.value
    return {
        skill.name: (
            natural_skill_rating(character, allocation, skill) if allocation is not None else 0
        )
        + granted.get(skill.name, 0)
        for skill in skills
    }


def _as_power_request(pick: tuple[str, int, str | None]) -> tuple[str, int, str | None]:
    power_id, rating, target = pick
    return power_id, rating, target or None


def create_power_selection(
    picks: Iterable[tuple[str, int, str | None]],
    catalog: Iterable[Power],
    power_point_budget: int,
    *,
    learned_skill_ratings: Mapping[str, int] | None = None,
    quality_names: Iterable[str] = (),
) -> PowerSelection:
    """Build a `PowerSelection`, validating every pick and the total Power Point spend together.

    `picks` is `(power_id, rating, target)` triples -- `target` (WP119; WP27's
    `selected_attribute`, widened) is required, and must be one of `power_target_options`, exactly
    when the power has a `target_kind`, and forbidden otherwise. Validates: every id resolves
    against `mvp_power_catalog(catalog)`; a power is bought at most `Power.limit` times, and a
    repeatable one never twice for the same target (Critical Strike "may be selected multiple
    times, each time for a different melee skill", p. 309); each rating is between 1 and
    `power_max_rating` (the Magic rating -- `power_point_budget` stands in for it, since an Adept's
    Power Points equal it -- and the power's `<maxlevels>`); and the summed cost (`points x rating
    + extra_point_cost`) doesn't exceed `power_point_budget`. Does not require the full budget to
    be spent, mirroring every other `create_*` function in this engine.

    **WP119**: `learned_skill_ratings` (skill name -> the rating bought for it, no Improvements),
    when given, checks Improved Ability: the skill must be known (p. 309, "You need to know the
    skill in order to buy this power for it") and the levels fit its half-the-rating cap. A save
    or import resolves powers before skills and passes none -- the same split WP115's
    `LaterStepFacts` makes for qualities.

    `quality_names` are the character's qualities: a power may not forbid one of them (Pain
    Resistance and High Pain Tolerance, p. 74).
    """
    offered_by_id = {p.id: p for p in mvp_power_catalog(catalog)}
    entries = [_as_power_request(pick) for pick in picks]
    ids = [power_id for power_id, _, _ in entries]

    unknown = sorted({pid for pid in ids if pid not in offered_by_id})
    if unknown:
        raise ValueError(f"not an MVP-offered power id: {unknown}")

    # A power that names nothing is bought once and levelled; `<limit>` caps a repeatable one's
    # instances.
    over_limit = sorted(
        {
            offered_by_id[pid].name
            for pid in ids
            if ids.count(pid) > (offered_by_id[pid].limit if offered_by_id[pid].repeatable else 1)
        }
    )
    if over_limit:
        raise ValueError(f"power selected more than once: {over_limit}")
    instances = [(pid, target) for pid, _, target in entries if offered_by_id[pid].repeatable]
    repeated = sorted(
        {offered_by_id[pid].name for pid, t in instances if instances.count((pid, t)) > 1}
    )
    if repeated:
        raise ValueError(f"the same power was bought twice for one target: {repeated}")

    held = set(quality_names)
    resolved: list[PowerPick] = []
    total_cost = Decimal(0)
    for power_id, rating, target in entries:
        power = offered_by_id[power_id]
        conflicts = sorted(held & set(power.forbidden_qualities))
        if conflicts:
            raise ValueError(f"{power.name!r} cannot be taken together with: {conflicts}")

        if power.target_kind is None:
            if target is not None:
                raise ValueError(f"{power.name!r} does not take a target, got {target!r}")
        elif power.target_kind == "text":
            if target is None or not target.strip():
                raise ValueError(f"{power.name!r} requires a detail")
            target = target.strip()
        else:
            options = power_target_options(power)
            if target not in options:
                raise ValueError(f"{power.name!r} needs one of {list(options)}, got {target!r}")

        learned = None
        if learned_skill_ratings is not None and power.target_minimum_rating and target:
            learned = learned_skill_ratings.get(target, 0)
            if learned < power.target_minimum_rating:
                raise ValueError(
                    f"{power.name!r} needs {target} at rating {power.target_minimum_rating} or "
                    f"higher; it is at {learned}"
                )

        if not power.levels and rating != 1:
            raise ValueError(f"{power.name!r} has no levels; rating must be 1, got {rating}")
        max_rating = power_max_rating(power, power_point_budget, learned)
        if rating < 1 or rating > max_rating:
            raise ValueError(
                f"{power.name!r}: rating {rating} is out of range 1..{max_rating} "
                f"(the power's own maximum, the Magic rating {power_point_budget}, and for "
                f"Improved Ability half the skill's rating)"
            )

        pick = PowerPick(power=power, rating=rating, target=target)
        resolved.append(pick)
        total_cost += pick.power_points

    if total_cost > power_point_budget:
        raise ValueError(
            f"{total_cost} Power Points spent, exceeding the budget of {power_point_budget}"
        )

    return PowerSelection(
        picks=tuple(resolved), power_points_spent=total_cost, power_point_budget=power_point_budget
    )


def apply_power_improvements(character: Character, selection: PowerSelection) -> None:
    """Add every purchased power's `PowerFlatBonus`es to `character.improvements`.

    Mirrors `chummer5.engine.qualities.apply_quality_improvements`'s shape: `source_id` is the
    power's own id (unique per selection, since `create_power_selection` rejects a duplicate pick),
    so a later removal can retract exactly what one power granted via `ImprovementIndex.remove_
    source(ImprovementSource.ADEPT_POWER, power.id)`. `value` is always `pick.rating` -- every
    verified `FLAT_BONUS` power's per-level magnitude is exactly 1 (see `chummer5.data.powers`'
    module docstring), so the purchased rating *is* the resolved bonus, with no further per-level
    multiplication needed.
    """
    for pick in selection.picks:
        for flat_bonus in pick.power.flat_bonuses:
            # An empty target on a target-taking power means "what this instance names" (WP119).
            target = flat_bonus.target_name or pick.target or ""
            character.improvements.add(
                Improvement(
                    improvement_type=_POWER_TARGET_KIND_TO_IMPROVEMENT_TYPE[flat_bonus.target_kind],
                    target=target,
                    value=pick.rating,
                    source_type=ImprovementSource.ADEPT_POWER,
                    source_id=pick.power.id,
                    unique_name=flat_bonus.unique_name,
                )
            )
