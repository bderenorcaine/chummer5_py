"""Skill allocation & dice pools.

Composes WP3's skill catalog (`chummer5.data.skills`) and WP2's Skills-priority data
(`chummer5.data.priorities`) with WP6's `Character` into a buildable skill point spend and the
dice-pool formula it feeds. Mundane MVP scope only — see `spec/Project Overview.md`.

Checked directly against `legacy/Chummer/Backend/Skills/Skill.cs` (`Base`, `LearnedRating`,
`TotalBaseRating`, `Rating`, `RatingMaximum`, `PoolOtherAttribute`, `DefaultModifier`,
`GetSpecializationBonus`) and `SkillGroup.cs` (`Base`), and cross-checked against
`Yeti-#ffffff2.chum5` (the corpus's one `buildmethod == Priority` fixture, also usable here for the
same reason WP6 used it for attributes: skill allocation doesn't depend on the Talent/magic path).
See `spec/worklogs/WP7.md` for the rules research this was checked against, including two points
that don't show up in `Implementation Plan.md`'s one-line summary of this WP:

- **Skill groups override, not add to, member skills' individual points.** Confirmed against
  legacy's default `StrictSkillGroupsInCreateMode = True`: a skill's rating comes from its group's
  points if the group has any spent, never from its own `skill_points` at the same time. Verified
  against Yeti: every skill belonging to a group with nonzero group points (Firearms, Stealth) has
  zero of its own base points in the save, and every skill with nonzero base points belongs to a
  group that itself has zero group points (Cracking, Tasking, Electronics, all unbought). WP7
  enforces this as a construction-time rule (`create_skill_allocation` rejects the conflicting
  combination) rather than silently letting one side win.
- **Karma-bought skill points are out of scope**, mirroring WP6's undocumented-but-consistent
  precedent for attributes (WP6 never modeled karma-bought points beyond the priority budget
  either). Two of Yeti's skills (Compiling, Computer) have nonzero `<karma>` on top of `<base>`;
  `create_skill_allocation`/`skill_rating` only ever consume `<base>` (the priority-budget-funded
  points), so a fully karma-complete rating isn't reproduced. This is a real, deliberate scope cut,
  not an oversight — flagged explicitly here (unlike WP6) so a future reader doesn't have to
  rediscover it. There's nothing in the corpus that stores a skill's *computed dice pool* to check
  against anyway (see below), so this cut costs no test coverage for this WP.

**WP50 — Step Five's skill-point-funded specialization.** Confirmed via `pdftotext -layout` against
the core rulebook's own "Purchase Skills" step (p.88, chapter 2) — see
`spec/rulebooks/learnings.md`'s WP50 entry for the full citation — and cross-checked against the
Skills chapter's own "SPECIALIZATIONS" section (p.129): a specialization costs 1 skill point (spent
from the same pool `skill_points` already draws from, on top of whatever points bought the skill's
own rating), grants `SPECIALIZATION_BONUS` (+2) to that narrow area, and is capped at exactly one
per skill at character creation. Two restrictions, both enforced by `create_skill_allocation`:

- **A skill group cannot be specialized in Step Five at all.** The rulebook is explicit that buying
  a specialization for a skill within a purchased group permanently breaks that group, and "this
  cannot happen in Step Five of character creation — you can only break up a skill group by buying
  a specialization for it in Step Seven" (p.88; Step Seven's group-breaking case is Phase O's WP53,
  not this one). Enforced here as "a specialization's skill must already have its own
  `skill_points` entry of at least 1" — which the existing "strict skill groups" rule already
  guarantees can't coexist with that skill's group having any points spent, so no separate group
  check is needed.
- **You have to have the skill first (Rating >= 1).** Skills chapter, p.129: "If you want a
  specialization in a skill, you have to have it first (meaning a Rating of at least 1)." Same
  `skill_points.get(skill_id, 0) >= 1` check as above covers this too.

`SkillAllocation.specializations` is a `dict[skill_id, name]` — keying by skill id both encodes "at
most one specialization per skill" for free (a dict can't have two values for the same key) and
mirrors `skill_points`/`group_points`'s own keying. The specialization's *name* (e.g. "Axes",
"Revolvers") is freeform player-authored text, not a catalog entry — SR5 doesn't enumerate valid
specialization names, mirroring `chummer5.engine.knowledge.KnowledgeSkillPick`'s identical "no
catalog, the player invents it" shape.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from chummer5.data.priorities import PriorityTable
from chummer5.data.skills import Skill
from chummer5.engine.character import Character
from chummer5.engine.improvements import ImprovementType

# CharacterSettings.MaxSkillRatingCreate (legacy default, confirmed in CharacterSettings.cs:
# `_intMaxSkillRatingCreate = 6`) -- the chargen-time cap on both individual skill and skill group
# rating; SR5's post-creation cap (`MaxSkillRating = 12`) doesn't apply to MVP, which only builds
# freshly-created characters.
MAX_SKILL_RATING_CREATE = 6

# CharacterSettings.SpecializationBonus -- flat dice pool bonus for a specialized test with that
# skill. (Legacy also has `ExpertiseBonus` for a stacked "Expertise" specialization tier; not
# modeled -- MVP's specialization support is the plain +2 case only.)
SPECIALIZATION_BONUS = 2

# Skill.DefaultModifier's unconditional case (-1) -- the dice pool penalty for using a skill
# "untrained" (rating 0, `can_default = True`). Legacy has several Improvement-driven ways to zero
# this out (Reflex Recorder, RemoveSkillDefaultPenalty, ...); none are in MVP scope.
DEFAULT_MODIFIER = -1


@dataclass(frozen=True)
class SkillPointBudget:
    """One Skills-priority-letter's point pools, split the same way `priorities.xml` splits them."""

    skills: int
    skill_groups: int


def skill_point_budget(letter: str, priorities: PriorityTable) -> SkillPointBudget:
    skills_priority = priorities.skills[letter]
    return SkillPointBudget(
        skills=skills_priority.skills, skill_groups=skills_priority.skill_groups
    )


@dataclass(frozen=True)
class SkillAllocation:
    """Points spent on individual skills and skill groups from one Skills-priority-letter budget.

    `skill_points` is keyed by `Skill.id` (stable, unambiguous -- matches how `LegacySkill.suid`
    cross-references the catalog, per WP4). `group_points` is keyed by skill group name (skill
    groups have no id in `skills.xml`, only a name -- same choice WP4's `LegacySkillGroup` already
    made).
    """

    skill_points: MappingProxyType[str, int]
    group_points: MappingProxyType[str, int]
    # WP50: skill_id -> specialization name, freeform player-authored text (see module docstring).
    specializations: MappingProxyType[str, str] = MappingProxyType({})


def create_skill_allocation(
    letter: str,
    priorities: PriorityTable,
    skills: tuple[Skill, ...],
    skill_points: Mapping[str, int],
    group_points: Mapping[str, int],
    specializations: Mapping[str, str] = MappingProxyType({}),
) -> SkillAllocation:
    """Build a `SkillAllocation`, validating the spend against the Skills-priority-letter budget.

    Validates: every `skill_points` key is a known `Skill.id`; every `group_points` key is a group
    name actually used by at least one skill; no negative spend; no single skill or group rated
    above `MAX_SKILL_RATING_CREATE`; no skill has its own `skill_points` entry while its group also
    has `group_points` spent (the "strict skill groups" rule -- see module docstring); and total
    spend in each pool doesn't exceed that pool's budget for `letter`. Does not require the full
    budget to be spent, mirroring WP6's `create_character`.

    WP50: every `specializations` key must be a known `Skill.id` with a nonblank name and at least 1
    of its own `skill_points` (see module docstring for why this alone enforces both "no skill group
    specializations in Step Five" and "you have to have the skill first"). Each specialization costs
    1 additional skill point, counted against the same `skill_points` budget.
    """
    skills_by_id = {s.id: s for s in skills}
    unknown_skills = set(skill_points) - set(skills_by_id)
    if unknown_skills:
        raise ValueError(f"not a known skill id: {sorted(unknown_skills)}")

    group_names = {s.skill_group for s in skills if s.skill_group is not None}
    unknown_groups = set(group_points) - group_names
    if unknown_groups:
        raise ValueError(f"not a known skill group: {sorted(unknown_groups)}")

    for skill_id, points in skill_points.items():
        if points < 0:
            raise ValueError(f"{skill_id}: points spent must not be negative, got {points}")
        if points > MAX_SKILL_RATING_CREATE:
            raise ValueError(
                f"{skill_id}: {points} exceeds the chargen skill rating maximum of "
                f"{MAX_SKILL_RATING_CREATE}"
            )
        group = skills_by_id[skill_id].skill_group
        if group is not None and group_points.get(group, 0) > 0:
            raise ValueError(
                f"{skill_id}: cannot spend points directly while its group {group!r} also has "
                f"points spent (strict skill groups)"
            )

    for group, points in group_points.items():
        if points < 0:
            raise ValueError(f"{group}: points spent must not be negative, got {points}")
        if points > MAX_SKILL_RATING_CREATE:
            raise ValueError(
                f"{group}: {points} exceeds the chargen skill rating maximum of "
                f"{MAX_SKILL_RATING_CREATE}"
            )

    unknown_spec_skills = set(specializations) - set(skills_by_id)
    if unknown_spec_skills:
        raise ValueError(f"not a known skill id: {sorted(unknown_spec_skills)}")

    for skill_id, name in specializations.items():
        if not name.strip():
            raise ValueError(f"{skill_id}: a specialization's name must not be blank")
        if skill_points.get(skill_id, 0) < 1:
            raise ValueError(
                f"{skill_id}: cannot add a specialization without at least 1 point spent "
                "directly on the skill (a skill group cannot be specialized in Step Five, and "
                "you must have the skill before specializing it)"
            )

    budget = skill_point_budget(letter, priorities)
    skills_spent = sum(skill_points.values()) + len(specializations)
    if skills_spent > budget.skills:
        raise ValueError(
            f"skill point spend {skills_spent} (including {len(specializations)} "
            f"specialization(s)) exceeds Skills priority {letter}'s budget of {budget.skills}"
        )
    groups_spent = sum(group_points.values())
    if groups_spent > budget.skill_groups:
        raise ValueError(
            f"skill group point spend {groups_spent} exceeds Skills priority {letter}'s budget of "
            f"{budget.skill_groups}"
        )

    return SkillAllocation(
        skill_points=MappingProxyType(dict(skill_points)),
        group_points=MappingProxyType(dict(group_points)),
        specializations=MappingProxyType(dict(specializations)),
    )


def skill_rating(character: Character, allocation: SkillAllocation, skill: Skill) -> int:
    """`Skill.Rating`: a skill's group rating if its group has points spent, else its own points,
    plus Σ improvements, capped at `MAX_SKILL_RATING_CREATE`.
    """
    group_rating = (
        allocation.group_points.get(skill.skill_group, 0) if skill.skill_group is not None else 0
    )
    points = group_rating if group_rating > 0 else allocation.skill_points.get(skill.id, 0)
    bonus = character.improvements.resolve(ImprovementType.SKILL, skill.name)
    return min(points + bonus, MAX_SKILL_RATING_CREATE)


def dice_pool(
    character: Character,
    allocation: SkillAllocation,
    skill: Skill,
    specialized: bool | None = None,
) -> int:
    """`Skill.PoolOtherAttribute`'s unconditional core: rating + linked attribute (+2 if
    specialized, at rating > 0 and not exotic), or the -1 "defaulting" penalty at rating 0 for
    skills that allow it, or 0 otherwise. Wound/sustaining penalties and Improvement-driven pool
    modifiers beyond `ImprovementType.SKILL` are out of MVP scope -- nothing in the MVP Improvement
    engine (WP5/WP8) produces one.

    WP50: `specialized` defaults to whether `skill.id` has an entry in
    `allocation.specializations` -- pass an explicit `True`/`False` to override (e.g. a synthetic
    what-if preview with no real `SkillAllocation` behind it).
    """
    if specialized is None:
        specialized = skill.id in allocation.specializations
    rating = skill_rating(character, allocation, skill)
    attribute_value = character.attribute_value(skill.attribute)
    if rating > 0:
        spec_bonus = SPECIALIZATION_BONUS if specialized and not skill.exotic else 0
        return max(0, rating + attribute_value + spec_bonus)
    if skill.can_default:
        return max(0, attribute_value + DEFAULT_MODIFIER)
    return 0
